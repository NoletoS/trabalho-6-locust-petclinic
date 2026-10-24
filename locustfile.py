"""Perfis do TP06. As rotas são as do gateway do PetClinic fixado no README."""

import csv
import os
import random
import time
import uuid
from pathlib import Path

from locust import HttpUser, between, events, task


CUSTOMERS = "/api/customer"
VETS = "/api/vet"
_started = None
_writer = None
_file = None


@events.test_start.add_listener
def start_capture(environment, **_kwargs):
    global _started, _writer, _file
    _started = time.monotonic()
    marker = os.environ.get("TP06_START_FILE")
    if marker:
        Path(marker).write_text(f"{time.time():.6f}", encoding="utf-8")
    output = os.environ.get("TP06_REQUEST_CSV")
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        _file = path.open("w", newline="", encoding="utf-8")
        _writer = csv.writer(_file)
        _writer.writerow(["epoch_s", "elapsed_s", "method", "operation", "response_ms", "failed"])


@events.request.add_listener
def capture_request(request_type, name, response_time, exception, **_kwargs):
    if _writer is None or _started is None:
        return
    elapsed = time.monotonic() - _started
    if elapsed < int(os.environ.get("TP06_WARMUP_S", "60")):
        return
    _writer.writerow([f"{time.time():.6f}", f"{elapsed:.6f}", request_type, name,
                      f"{response_time:.3f}", int(exception is not None)])


@events.test_stop.add_listener
def stop_capture(environment, **_kwargs):
    global _file, _writer
    if _file:
        _file.close()
    _file = None
    _writer = None


class PetClinicUser(HttpUser):
    abstract = True
    wait_time = between(0.5, 1.5)

    def on_start(self):
        ids = os.environ.get("TP06_OWNER_IDS", "1").split(",")
        self.owner_ids = [int(value) for value in ids if value.strip()]

    def list_owners(self):
        with self.client.get(f"{CUSTOMERS}/owners", name="GET /owners", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
            else:
                try:
                    if not isinstance(response.json(), list):
                        response.failure("Resposta de owners não é lista JSON")
                except ValueError:
                    response.failure("JSON inválido em owners")

    def get_owner(self):
        owner_id = random.choice(self.owner_ids)
        with self.client.get(f"{CUSTOMERS}/owners/{owner_id}", name="GET /owners/{id}", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
            else:
                try:
                    if response.json().get("id") != owner_id:
                        response.failure("ID divergente em owner")
                except (ValueError, AttributeError):
                    response.failure("JSON inválido em owner")

    def list_vets(self):
        with self.client.get(f"{VETS}/vets", name="GET /vets", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
            else:
                try:
                    if not isinstance(response.json(), list):
                        response.failure("Resposta de vets não é lista JSON")
                except ValueError:
                    response.failure("JSON inválido em vets")

    def create_owner(self):
        token = uuid.uuid4().hex[:12]
        payload = {"firstName": "Carga", "lastName": f"Teste{token}",
                   "address": "Rua Experimental 1", "city": "Teste", "telephone": "11999999999"}
        with self.client.post(f"{CUSTOMERS}/owners", json=payload,
                              name="POST /owners", catch_response=True) as response:
            if response.status_code != 201:
                response.failure(f"HTTP {response.status_code}")
            else:
                try:
                    if not isinstance(response.json().get("id"), int):
                        response.failure("POST sem ID numérico")
                except (ValueError, AttributeError):
                    response.failure("JSON inválido no POST")


class LeituraUser(PetClinicUser):
    @task(45)
    def owners(self):
        self.list_owners()

    @task(35)
    def owner(self):
        self.get_owner()

    @task(15)
    def vets(self):
        self.list_vets()

    @task(5)
    def post_owner(self):
        self.create_owner()


class EscritaUser(PetClinicUser):
    @task(20)
    def owners(self):
        self.list_owners()

    @task(20)
    def owner(self):
        self.get_owner()

    @task(20)
    def vets(self):
        self.list_vets()

    @task(40)
    def post_owner(self):
        self.create_owner()
