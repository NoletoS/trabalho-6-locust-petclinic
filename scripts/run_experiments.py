"""Executa as 60 rodadas somente quando invocado explicitamente pelo usuário."""

import argparse
import csv
import http.client
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {"A": 30, "B": 80, "C": 150}
PROFILES = {"leitura": "LeituraUser", "escrita": "EscritaUser"}
CONTAINERS = ("api-gateway", "customers-service", "vets-service")
UPSTREAM = ROOT / "petclinic-upstream"
TOTAL_S = 360
WARMUP_S = 60


def set_system_awake(enabled):
    """Evita suspensão automática do Windows enquanto a campanha está ativa."""
    if os.name == "nt":
        import ctypes
        continuous = 0x80000000
        system_required = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            continuous | system_required if enabled else continuous)


def get_json(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        return json.load(response)


def get_json_retry(url, wait_s=90):
    """Aguarda o gateway estabilizar após reiniciar customers-service."""
    deadline = time.monotonic() + wait_s
    while True:
        try:
            return get_json(url)
        except (urllib.error.URLError, http.client.HTTPException, OSError,
                ValueError, RuntimeError) as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Rota indisponível após {wait_s}s: {url}: {error}") from error
            time.sleep(3)


def post_owner_retry(host, payload, last_name, wait_s=90):
    """Repete falhas transitórias do POST sem criar um segundo owner após resposta perdida."""
    deadline = time.monotonic() + wait_s
    url = host + "/api/customer/owners"
    while True:
        request = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status != 201:
                    raise RuntimeError(f"POST /owners: HTTP {response.status}")
                return json.load(response)
        except (urllib.error.URLError, http.client.HTTPException, OSError,
                ValueError, RuntimeError) as error:
            try:
                owners = get_json(url)
                matches = [owner for owner in owners if isinstance(owner, dict)
                           and owner.get("lastName") == last_name]
                if len(matches) == 1 and isinstance(matches[0].get("id"), int):
                    return matches[0]
            except (urllib.error.URLError, http.client.HTTPException, OSError,
                    ValueError, RuntimeError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f"POST /owners indisponível após {wait_s}s: {error}") from error
            time.sleep(3)


def preflight(host):
    owners = get_json_retry(host + "/api/customer/owners")
    vets = get_json_retry(host + "/api/vet/vets")
    if not isinstance(owners, list) or not isinstance(vets, list):
        raise RuntimeError("Owners e vets devem retornar listas JSON")
    token = str(time.time_ns())
    payload = json.dumps({"firstName": "Preflight", "lastName": token,
                          "address": "Rua Experimental 1", "city": "Teste",
                          "telephone": "11999999999"}).encode()
    created = post_owner_retry(host, payload, token)
    owner_id = created.get("id")
    if not isinstance(owner_id, int):
        raise RuntimeError("POST /owners não retornou ID numérico")
    if get_json_retry(host + f"/api/customer/owners/{owner_id}").get("id") != owner_id:
        raise RuntimeError("GET /owners/{id} não retornou o proprietário criado")
    if len(get_json_retry(host + "/api/customer/owners")) != len(owners) + 1:
        raise RuntimeError("Pré-verificação alterou inesperadamente a quantidade de owners")
    ids = [item.get("id") for item in owners if isinstance(item, dict)] + [owner_id]
    ids = [value for value in ids if isinstance(value, int)]
    return sorted(set(ids))


def reset_customers(host):
    """Reinicia o HSQLDB em memória e espera a base inicial de 10 proprietários."""
    if not (UPSTREAM / "docker-compose.yml").is_file():
        raise RuntimeError(f"Compose do PetClinic não encontrado em {UPSTREAM}")
    subprocess.run(["docker", "compose", "restart", "customers-service"], cwd=UPSTREAM,
                   capture_output=True, text=True, timeout=90, check=True)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            direct = get_json("http://localhost:8081/owners")
            routed = get_json(host + "/api/customer/owners")
            if isinstance(direct, list) and isinstance(routed, list) and len(direct) == len(routed) == 10:
                return
        except (urllib.error.URLError, http.client.HTTPException, OSError, RuntimeError, ValueError):
            pass
        time.sleep(3)
    raise RuntimeError("customers-service não voltou à base inicial de 10 proprietários")


def cpu_monitor(path, marker, process, stop):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["epoch_s", "elapsed_s", "container", "cpu_percent"])
        while not stop.is_set() and process.poll() is None:
            try:
                start = float(marker.read_text(encoding="utf-8"))
                command = ["docker", "stats", "--no-stream", "--format",
                           "{{.Name}},{{.CPUPerc}}", *CONTAINERS]
                result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=True)
                now = time.time()
                for line in result.stdout.splitlines():
                    name, percent = line.rsplit(",", 1)
                    if name in CONTAINERS:
                        writer.writerow([f"{now:.6f}", f"{now - start:.6f}",
                                         name, percent.strip().rstrip("%")])
                stream.flush()
            except FileNotFoundError:
                pass  # O marcador ainda não foi escrito pelo Locust.
            except (ValueError, subprocess.SubprocessError) as error:
                print(f"Aviso: coleta de CPU: {error}", file=sys.stderr)
            stop.wait(5)


def run_one(host, profile, scenario, repetition, output):
    reset_customers(host)
    ids = preflight(host)
    output.mkdir(parents=True, exist_ok=False)
    marker = output / "start_epoch.txt"
    env = os.environ.copy()
    env.update({"TP06_REQUEST_CSV": str(output / "requests.csv"),
                "TP06_START_FILE": str(marker), "TP06_WARMUP_S": str(WARMUP_S),
                "TP06_OWNER_IDS": ",".join(map(str, ids))})
    command = [sys.executable, "-m", "locust", "-f", str(ROOT / "locustfile.py"),
               PROFILES[profile], "--headless", "--host", host,
               "--users", str(SCENARIOS[scenario]), "--spawn-rate", "15",
               "--run-time", f"{TOTAL_S}s", "--stop-timeout", "5",
               "--exit-code-on-error", "0", "--only-summary",
               "--csv", str(output / "locust"), "--csv-full-history"]
    metadata = {"profile": profile, "scenario": scenario, "users": SCENARIOS[scenario],
                "repetition": repetition, "duration_s": TOTAL_S,
                "warmup_s": WARMUP_S, "measured_s": TOTAL_S - WARMUP_S,
                "host": host, "owner_ids_at_start": len(ids),
                "database_reset": "docker compose restart customers-service; 10 owners confirmados",
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "command_for_reproduction": [part.replace(str(ROOT) + os.sep, "") for part in command]}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    stop = threading.Event()
    with (output / "locust.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        monitor = threading.Thread(target=cpu_monitor,
                                  args=(output / "cpu.csv", marker, process, stop), daemon=True)
        monitor.start()
        try:
            return_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise
        finally:
            stop.set()
            monitor.join(timeout=25)
    metadata["ended_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["return_code"] = return_code
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if not completed(output):
        raise RuntimeError(f"Rodada incompleta ou CPU sem cobertura até o fim: {output}; consulte locust.log e cpu.csv")


def completed(output):
    """Considera concluída apenas uma rodada encerrada normalmente com arquivos úteis."""
    metadata = output / "metadata.json"
    requests = output / "requests.csv"
    cpu = output / "cpu.csv"
    if not all(path.is_file() for path in (metadata, requests, cpu)):
        return False
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
        if data.get("return_code") != 0 or requests.stat().st_size <= 80:
            return False
        samples = {name: [] for name in CONTAINERS}
        with cpu.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                elapsed = float(row["elapsed_s"])
                if row["container"] in samples and WARMUP_S <= elapsed < TOTAL_S:
                    samples[row["container"]].append(elapsed)
        return all(len(times) >= 20 and min(times) <= 75 and max(times) >= 345
                   for times in samples.values())
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://localhost:8080")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "raw")
    parser.add_argument("--single", nargs=3, metavar=("PROFILE", "SCENARIO", "REP"),
                        help="Executa só uma rodada, por exemplo: leitura A 1")
    args = parser.parse_args()
    host = args.host.rstrip("/")
    if args.repetitions < 1:
        parser.error("--repetitions deve ser positivo")
    if args.single:
        profile, scenario, rep_text = args.single
        if profile not in PROFILES or scenario not in SCENARIOS or not rep_text.isdigit() or int(rep_text) < 1:
            parser.error("--single requer perfil leitura/escrita, cenário A/B/C e repetição positiva")
        plan = [(profile, scenario, int(rep_text))]
    else:
        plan = []
        rng = random.Random(20261023)
        for repetition in range(1, args.repetitions + 1):
            configurations = [(p, s, repetition) for p in PROFILES for s in SCENARIOS]
            rng.shuffle(configurations)
            plan.extend(configurations)
    set_system_awake(True)
    try:
        print(f"Plano: {len(plan)} rodadas de {TOTAL_S // 60} min; primeiro minuto é aquecimento.", flush=True)
        for number, (profile, scenario, repetition) in enumerate(plan, 1):
            output = args.results / f"{profile}_{scenario}_{repetition:02d}"
            if output.exists():
                if completed(output):
                    print(f"[{number}/{len(plan)}] já concluída, preservada: {output.name}", flush=True)
                    continue
                archive_dir = args.results.parent / "interrupted"
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive = archive_dir / (output.name + ".interrompida_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
                if archive.exists():
                    raise RuntimeError(f"Nome de arquivo já existe: {archive}")
                output.rename(archive)
                print(f"Rodada incompleta preservada em {archive.name}; será refeita.", flush=True)
            print(f"[{number}/{len(plan)}] {profile} {scenario} repetição {repetition}", flush=True)
            run_one(host, profile, scenario, repetition, output)
        if args.single:
            print("Rodada concluída e preservada.", flush=True)
        else:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze.py"),
                            "--repetitions", str(args.repetitions)], cwd=ROOT, check=True)
            print("Todas as rodadas, tabelas e gráficos foram concluídos.", flush=True)
    finally:
        set_system_awake(False)


if __name__ == "__main__":
    main()
