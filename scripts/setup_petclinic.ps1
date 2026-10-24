param([string]$Destination = "petclinic-upstream", [switch]$BuildFromSource)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$target = Join-Path $root $Destination
$revision = "1d76b00d683e86b62867a6bf59530f8ab301244f"
if (Test-Path -LiteralPath $target) {
    throw "O diretório já existe: $target. Use o checkout existente ou indique outro destino."
}
git clone https://github.com/spring-petclinic/spring-petclinic-microservices.git $target
if ($LASTEXITCODE -ne 0) { throw "Falha no git clone" }
Push-Location $target
try {
    git checkout $revision
    if ($LASTEXITCODE -ne 0) { throw "Falha ao fixar a revisão" }
    if ($BuildFromSource) {
        .\mvnw.cmd clean install -PbuildDocker
        if ($LASTEXITCODE -ne 0) { throw "Falha no build das imagens" }
        docker compose up -d config-server discovery-server customers-service vets-service visits-service api-gateway
    }
    else {
        docker compose -f docker-compose.yml -f ..\docker-compose.images.yml up -d config-server discovery-server customers-service vets-service visits-service api-gateway
    }
    if ($LASTEXITCODE -ne 0) { throw "Falha no Docker Compose" }
    Write-Host "PetClinic iniciado. Aguarde todos os serviços e verifique http://localhost:8080"
}
finally {
    Pop-Location
}
