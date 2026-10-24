"""Consolida os CSVs reais, gera gráficos e preenche a análise do README."""

import argparse
import csv
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run_experiments import completed


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SCENARIOS = ("A", "B", "C")
PROFILES = ("leitura", "escrita")
OPERATIONS = ("GET /owners", "GET /owners/{id}", "GET /vets", "POST /owners")
SERVICES = ("api-gateway", "customers-service", "vets-service")


def rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        yield from csv.DictReader(stream)


def p95(values):
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def measure(requests):
    if not requests:
        raise ValueError("Janela de medição sem requisições")
    times = [item["response_ms"] for item in requests]
    failures = sum(item["failed"] for item in requests)
    return {"mean_ms": statistics.mean(times), "p95_ms": p95(times),
            "rps": len(requests) / 300, "success_rps": (len(requests) - failures) / 300,
            "requests": len(requests),
            "failure_pct": 100 * failures / len(requests)}


def write_csv(path, fieldnames, records):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def fmt(value, digits=2):
    return f"{value:.{digits}f}"


def md_table(headers, records):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(map(str, record)) + " |" for record in records)
    return "\n".join(lines)


def plot_metric(summary, metric, label, file):
    fig, ax = plt.subplots(figsize=(7, 4))
    for profile in PROFILES:
        ax.plot(SCENARIOS, [summary[(profile, s)][metric] for s in SCENARIOS],
                marker="o", label=profile.capitalize())
    ax.set(xlabel="Cenário (30, 80, 150 usuários)", ylabel=label)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "graphs" / file, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=10)
    args = parser.parse_args()
    raw = RESULTS / "raw"
    run_records = []
    operation_records = []
    cpu_records = []
    for profile in PROFILES:
        for scenario in SCENARIOS:
            for repetition in range(1, args.repetitions + 1):
                folder = raw / f"{profile}_{scenario}_{repetition:02d}"
                if not completed(folder):
                    raise SystemExit(f"Rodada incompleta ou CPU sem cobertura até o fim: {folder}")
                request_file, cpu_file = folder / "requests.csv", folder / "cpu.csv"
                if not request_file.exists() or not cpu_file.exists():
                    raise SystemExit(f"Falta rodada ou CSV obrigatório: {folder}")
                requests = []
                for row in rows(request_file):
                    elapsed = float(row["elapsed_s"])
                    if 60 <= elapsed < 360:
                        requests.append({"operation": row["operation"],
                                         "response_ms": float(row["response_ms"]),
                                         "failed": int(row["failed"])})
                if not requests:
                    raise SystemExit(f"Sem requisições na janela útil: {folder}")
                base = {"profile": profile, "scenario": scenario, "users": {"A": 30, "B": 80, "C": 150}[scenario],
                        "repetition": repetition}
                run_records.append(base | measure(requests))
                for operation in OPERATIONS:
                    selected = [item for item in requests if item["operation"] == operation]
                    if not selected:
                        raise SystemExit(f"Operação ausente em {folder}: {operation}")
                    operation_records.append(base | {"operation": operation} | measure(selected))
                cpu_by_service = defaultdict(list)
                for row in rows(cpu_file):
                    if 60 <= float(row["elapsed_s"]) < 360:
                        cpu_by_service[row["container"]].append(float(row["cpu_percent"]))
                for service in SERVICES:
                    samples = cpu_by_service[service]
                    if not samples:
                        raise SystemExit(f"Sem amostras de CPU de {service}: {folder}")
                    cpu_records.append(base | {"service": service, "cpu_mean_pct": statistics.mean(samples),
                                               "cpu_peak_pct": max(samples), "cpu_samples": len(samples)})

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "graphs").mkdir(exist_ok=True)
    write_csv(RESULTS / "runs.csv", list(run_records[0]), run_records)
    write_csv(RESULTS / "operations.csv", list(operation_records[0]), operation_records)
    write_csv(RESULTS / "cpu.csv", list(cpu_records[0]), cpu_records)

    summary = {}
    summary_records = []
    for profile in PROFILES:
        for scenario in SCENARIOS:
            group = [r for r in run_records if r["profile"] == profile and r["scenario"] == scenario]
            fields = ("mean_ms", "p95_ms", "rps", "success_rps", "requests", "failure_pct")
            record = {"profile": profile, "scenario": scenario, "users": group[0]["users"],
                      "repetitions": len(group)}
            record.update({key: statistics.mean(r[key] for r in group) for key in fields})
            summary[(profile, scenario)] = record
            summary_records.append(record)
    write_csv(RESULTS / "summary.csv", list(summary_records[0]), summary_records)

    run_totals = {(r["profile"], r["scenario"], r["repetition"]): r["requests"] for r in run_records}
    operation_summary_records = []
    for profile in PROFILES:
        for scenario in SCENARIOS:
            for operation in OPERATIONS:
                group = [r for r in operation_records if r["profile"] == profile
                         and r["scenario"] == scenario and r["operation"] == operation]
                record = {"profile": profile, "scenario": scenario, "operation": operation}
                record.update({key: statistics.mean(r[key] for r in group)
                               for key in ("mean_ms", "p95_ms", "rps", "success_rps", "requests", "failure_pct")})
                record["mix_pct"] = statistics.mean(
                    100 * r["requests"] / run_totals[(profile, scenario, r["repetition"])] for r in group)
                operation_summary_records.append(record)
    write_csv(RESULTS / "operations_summary.csv", list(operation_summary_records[0]), operation_summary_records)

    cpu_summary = {}
    cpu_summary_records = []
    for profile in PROFILES:
        for scenario in SCENARIOS:
            for service in SERVICES:
                group = [r for r in cpu_records if r["profile"] == profile and r["scenario"] == scenario
                         and r["service"] == service]
                value = statistics.mean(r["cpu_mean_pct"] for r in group)
                cpu_summary[(profile, scenario, service)] = value
                cpu_summary_records.append({"profile": profile, "scenario": scenario,
                                            "service": service, "cpu_mean_pct": value})
    write_csv(RESULTS / "cpu_summary.csv", list(cpu_summary_records[0]), cpu_summary_records)

    for metric, label, file in (("mean_ms", "Tempo médio (ms)", "response_mean.png"),
                                ("p95_ms", "P95 (ms)", "response_p95.png"),
                                ("rps", "Requisições/s (inclui falhas)", "throughput.png"),
                                ("success_rps", "Requisições bem-sucedidas/s", "successful_throughput.png"),
                                ("failure_pct", "Falhas (%)", "failures.png")):
        plot_metric(summary, metric, label, file)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, profile in zip(axes, PROFILES):
        for service in SERVICES:
            ax.plot(SCENARIOS, [cpu_summary[(profile, s, service)] for s in SCENARIOS],
                    marker="o", label=service)
        ax.set(title=profile.capitalize(), xlabel="Cenário", ylabel="CPU média (%)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "graphs" / "cpu.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, profile in zip(axes, PROFILES):
        for operation in OPERATIONS:
            ax.plot(SCENARIOS,
                    [next(r["p95_ms"] for r in operation_summary_records if r["profile"] == profile
                          and r["scenario"] == scenario and r["operation"] == operation)
                     for scenario in SCENARIOS], marker="o", label=operation)
        ax.set(title=profile.capitalize(), xlabel="Cenário", ylabel="P95 médio (ms)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "graphs" / "operations_p95.png", dpi=160)
    plt.close(fig)

    table = md_table(["Perfil", "Cenário", "Usuários", "Média ms", "P95 ms", "req/s", "req/s OK", "Req.", "Falhas %"],
                     [[r["profile"], r["scenario"], r["users"], fmt(r["mean_ms"]),
                       fmt(r["p95_ms"]), fmt(r["rps"]), fmt(r["success_rps"]), fmt(r["requests"], 1),
                       fmt(r["failure_pct"])] for r in summary_records])
    cpu_table = md_table(["Perfil", "Cenário", "Gateway %", "Customers %", "Vets %"],
                         [[p, s, *[fmt(cpu_summary[(p, s, service)]) for service in SERVICES]]
                          for p in PROFILES for s in SCENARIOS])
    operation_table = md_table(["Perfil", "Cenário", "Operação", "Peso observado %", "Média ms", "P95 ms", "Falhas %"],
                               [[r["profile"], r["scenario"], r["operation"], fmt(r["mix_pct"]),
                                 fmt(r["mean_ms"]), fmt(r["p95_ms"]), fmt(r["failure_pct"])]
                                for r in operation_summary_records])
    degradation = []
    for profile in PROFILES:
        for operation in OPERATIONS:
            means = {}
            for scenario in ("A", "C"):
                group = [r["p95_ms"] for r in operation_records if r["profile"] == profile
                         and r["scenario"] == scenario and r["operation"] == operation]
                means[scenario] = statistics.mean(group)
            degradation.append((profile, operation, means["C"] - means["A"],
                                means["C"] / means["A"] if means["A"] else float("inf")))
    degradation.sort(key=lambda row: row[2], reverse=True)
    worst = degradation[0]
    highest_failure = max(summary_records, key=lambda r: r["failure_pct"])
    throughput_winner = max(PROFILES, key=lambda p: statistics.mean(summary[(p, s)]["rps"] for s in SCENARIOS))
    successful_winner = max(PROFILES, key=lambda p: statistics.mean(summary[(p, s)]["success_rps"] for s in SCENARIOS))
    average_rps = {p: statistics.mean(summary[(p, s)]["rps"] for s in SCENARIOS) for p in PROFILES}
    average_success_rps = {p: statistics.mean(summary[(p, s)]["success_rps"] for s in SCENARIOS) for p in PROFILES}
    degradation_answer = (f"{worst[1]} no perfil {worst[0]}, com aumento de {fmt(worst[2])} ms no P95 médio de A para C ({fmt(worst[3])}×)."
                          if worst[2] > 0 else "Nenhuma operação teve aumento do P95 médio de A para C.")
    failure_answer = (f"{highest_failure['profile']} / cenário {highest_failure['scenario']}, {fmt(highest_failure['failure_pct'])}%."
                      if highest_failure["failure_pct"] > 0 else "Nenhum cenário apresentou falhas na janela medida.")
    cpu_changes = "; ".join(
        f"{service}: {fmt(cpu_summary[('leitura', 'A', service)])}→{fmt(cpu_summary[('leitura', 'C', service)])}% em leitura e "
        f"{fmt(cpu_summary[('escrita', 'A', service)])}→{fmt(cpu_summary[('escrita', 'C', service)])}% em escrita"
        for service in SERVICES
    )
    text = f"""### Resultados medidos

Valores são médias aritméticas das {args.repetitions} repetições por configuração. Cada rodada tem 6 min, dos quais os primeiros 60 s foram descartados; vazão usa 300 s como denominador. `req/s` inclui respostas com erro; `req/s OK` conta apenas respostas bem-sucedidas. P95 é calculado em cada rodada pelo posto mais próximo e depois promediado.

{table}

{cpu_table}

#### Operações

{operation_table}

![Tempo médio](results/graphs/response_mean.png)
![P95](results/graphs/response_p95.png)
![Vazão](results/graphs/throughput.png)
![Vazão bem-sucedida](results/graphs/successful_throughput.png)
![Falhas](results/graphs/failures.png)
![CPU](results/graphs/cpu.png)
![P95 por operação](results/graphs/operations_p95.png)

### Respostas às questões

1. **Usuários e tempo de resposta:** em leitura, a média subiu de {fmt(summary[("leitura", "A")]["mean_ms"])} ms (A) para {fmt(summary[("leitura", "B")]["mean_ms"])} ms (B) e {fmt(summary[("leitura", "C")]["mean_ms"])} ms (C). Em escrita, foi {fmt(summary[("escrita", "A")]["mean_ms"])} ms (A), {fmt(summary[("escrita", "B")]["mean_ms"])} ms (B) e {fmt(summary[("escrita", "C")]["mean_ms"])} ms (C). A queda aparente de B para C em escrita ocorre junto de {fmt(summary[("escrita", "C")]["failure_pct"])}% de falhas; respostas de erro rápidas reduzem a média, sem indicar melhora do serviço.
2. **Maior vazão:** {throughput_winner}, pela média de req/s dos três cenários ({fmt(average_rps['leitura'])} em leitura; {fmt(average_rps['escrita'])} em escrita). Em requisições bem-sucedidas/s, {successful_winner} também liderou ({fmt(average_success_rps['leitura'])} contra {fmt(average_success_rps['escrita'])}). O pico bruto de {fmt(summary[("escrita", "C")]["rps"])} req/s em escrita C contém muitas falhas; só {fmt(summary[("escrita", "C")]["success_rps"])} req/s tiveram sucesso.
3. **Maior degradação:** {degradation_answer} A comparação completa por operação está em `results/operations.csv`.
4. **CPU:** de A para C, {cpu_changes}. CPU do Docker pode superar 100% em múltiplos núcleos; é porcentagem de núcleo, não fração do limite da máquina. A CPU de customers em escrita C ficou abaixo de B ao mesmo tempo que a taxa de falhas aumentou muito; isso não demonstra ganho de eficiência.
5. **Maior taxa de falhas:** {failure_answer}

### Conclusões

Nesta campanha, **{throughput_winner}** teve a maior vazão média e **{successful_winner}** a maior vazão bem-sucedida. A maior degradação do P95 entre A e C foi {worst[1]} em {worst[0]}, com aumento de {fmt(worst[2])} ms. A maior taxa de falhas foi {failure_answer} Em escrita C, apenas {fmt(summary[("escrita", "C")]["success_rps"])} das {fmt(summary[("escrita", "C")]["rps"])} req/s médias tiveram sucesso. Não se deve interpretar o menor tempo médio desse cenário como melhora do atendimento.

Os logs do Locust registram HTTP 405 em GETs e HTTP 503 em POSTs. O gateway também registrou períodos sem instâncias disponíveis de `customers-service`; isso sustenta parte dos 503, mas os registros atuais não permitem atribuir com segurança todos os 405 a uma causa única. Portanto, as conclusões sobre degradação descrevem a **pilha implantada neste ambiente**, não isolam o desempenho interno de cada microsserviço. Os tempos de resposta incluem falhas; a vazão bem-sucedida ajuda a distinguir rapidez de erro de capacidade útil.

Os CSVs de cada execução em `results/raw/` são a evidência bruta. Os números refletem este ambiente e esta ordem de rodadas; criação de proprietários aumenta o tamanho da base dentro de cada rodada. Variações entre repetições e serviços concorrentes no host também limitam a generalização.
"""
    (RESULTS / "analysis.md").write_text(text.replace("](results/graphs/", "](graphs/"), encoding="utf-8")
    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    begin, end = "<!-- ANALYSIS_START -->", "<!-- ANALYSIS_END -->"
    if begin not in original or end not in original:
        raise SystemExit("Marcadores da análise não encontrados no README")
    insertion = original.split(begin)[0] + begin + "\n" + text + "\n" + end + original.split(end, 1)[1]
    insertion = re.sub(
        r"^\*\*Estado desta cópia:\*\*.*$",
        f"**Estado desta cópia:** {len(run_records)} rodadas foram consolidadas em `results/`; confira os CSVs brutos e complete o link do vídeo antes da entrega.",
        insertion, count=1, flags=re.MULTILINE
    ).replace("| CSVs das 60 rodadas | Aguardando execução |",
              "| CSVs das 60 rodadas | Disponíveis em `results/raw/` |").replace(
              "| Tabelas e gráficos | Aguardando execução |",
              "| Tabelas e gráficos | Disponíveis em `results/` |").replace(
              "| Descrição do ambiente em `results/environment.md` | A preencher na máquina de execução |",
              "| Descrição do ambiente em `results/environment.md` | Disponível em `results/environment.md` |")
    readme.write_text(insertion, encoding="utf-8")
    print("Gerados CSVs, gráficos, results/analysis.md e seção de resultados do README.")


if __name__ == "__main__":
    main()
