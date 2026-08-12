# Guia de Upload e Deploy na Hostinger VPS (`up_hostinger.md`)

Este documento explica como foi feito o upload de arquivos pesados (como o `saida_rasterio.parquet` de ~290MB) e como colocar a API para rodar na VPS da Hostinger sem precisar de SCP ou FTP.

---

## 💡 O Problema dos Arquivos Pesados

O GitHub tem um limite máximo recomendado de 50MB a 100MB por arquivo individual. Arquivos maiores que isso costumam ser rejeitados se você tentar fazer `git push` direto. Além disso, transferências por `scp` / `sftp` exigem configuração de chaves SSH ou senhas root expostas.

---

## 🛠️ A Solução: Divisão de Arquivos no Git (Chunking)

Para resolver isso de forma simples e 100% automatizada via Git, utilizamos a estratégia de **divisão de arquivos (chunking)**:

### 1. Divisão no ambiente Local (Windows/Python)
Localmente, executamos um script simples em Python que leu o arquivo `saida_rasterio.parquet` (~290MB) em blocos de 90MB e gerou 4 partes menores:
- `data/saida_rasterio.parquet.part1` (~90MB)
- `data/saida_rasterio.parquet.part2` (~90MB)
- `data/saida_rasterio.parquet.part3` (~90MB)
- `data/saida_rasterio.parquet.part4` (~8MB)

### 2. Configuração do `.gitignore`
Ajustamos o `.gitignore` para ignorar arquivos `.parquet` gigantes, porém aceitar as partes divididas:
```gitignore
*.parquet
!*.parquet.part*
```

### 3. Push para o GitHub
Subimos as 4 partes para o repositório GitHub normalmente via `git push origin main`.

---

## 🚀 Como Recompor e Subir no Servidor (VPS Hostinger)

No terminal da VPS, executamos os comandos para reconstituir o arquivo original e subir o ambiente:

### Passo 1: Baixar os arquivos atualizados
```bash
cd ~/hydro_osmnx_api
git pull origin main
```

### Passo 2: Juntar as partes no Linux (`cat`)
O comando `cat` no Linux concatena múltiplos arquivos em ordem sequencial:
```bash
cat data/saida_rasterio.parquet.part* > data/saida_rasterio.parquet
```

### Passo 3: Limpeza das partes temporárias
```bash
rm data/saida_rasterio.parquet.part*
```

### Passo 4: Criar o arquivo de ambiente
```bash
cp .env.example .env
```

### Passo 5: Subir os Containers Docker
*(Nota: Versões recentes do Docker usam `docker compose` com espaço, em vez de `docker-compose` com hífen)*:

```bash
docker compose up --build -d
```
> Se o comando acima não funcionar, instale o utilitário rodando `apt update && apt install -y docker-compose-plugin` ou `snap install docker`.
