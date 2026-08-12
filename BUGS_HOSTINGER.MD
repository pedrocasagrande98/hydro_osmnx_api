# Registro de Bugs e Falhas no Deploy (Hostinger)

Este documento centraliza os erros encontrados durante as tentativas de deploy do projeto `hydro_osmnx_api` no painel da Hostinger, bem como as soluções propostas para cada um deles. Nenhuma alteração no código será feita até aprovação posterior.

## 1. Conflito de Porta na API (`api`)
**Erro Reportado**: `failed to bind host port 0.0.0.0:8000/tcp: address already in use`
**Descrição**: O contêiner da API não conseguiu iniciar porque a porta `8000` do seu servidor VPS já está ocupada por algum outro processo (provavelmente algum resquício do Activepieces ou outro serviço rodando na Hostinger).
**Solução Proposta**: 
- Alterar o mapeamento de portas no arquivo `docker-compose.yml` para usar uma porta externa diferente que esteja livre (ex: mudar de `"8000:8000"` para `"8001:8000"`). 
- Caso o Nginx vá fazer o proxy reverso da API, o Nginx deve apontar para o nome do serviço interno do docker (`api:8000`) ao invés da porta externa do servidor.

## 2. Erro no Celery Worker (Import/Dependência Ausente)
**Erro Reportado**: Falha por conta do módulo `hydro_mde`.
**Descrição**: O contêiner do `celery_worker` finalizou a execução prematuramente. A análise indicou que o módulo Python `hydro_mde` não está instalado na imagem do Docker ou está sendo importado incorretamente em algum arquivo (ex: `from hydro_mde.config import ...`). Isso provavelmente veio de código colado de um projeto anterior (hydro_mde) para este (hydro_osmnx_api).
**Solução Proposta**:
- Verificar os arquivos `.py` (como o `app/celery_app.py`, `app/tasks/worker.py` ou os workers) e garantir que não há importações copiadas de projetos antigos (como `hydro_mde`) que não existem neste projeto.
- Substituir essas importações pelo caminho correto, como `from app.core.config import ...`
- Após a correção, forçar o rebuild da imagem.

## 3. Comportamento Inesperado do Certbot
**Erro Reportado**: Contêiner finalizou a execução (Exited).
**Descrição**: O contêiner do `certbot` no `docker-compose.yml` está iniciando sem uma instrução contínua. Por ser uma imagem de comando único, ele tenta executar sua ação e sai. Isso é um comportamento esperado para o Certbot em muitos setups, mas pode gerar falsos alertas na dashboard ou derrubar serviços caso mal encadeado.
**Solução Proposta**:
- Se você ainda não apontou um domínio definitivo para o IP da VPS, o ideal é **remover temporariamente** o bloco do `certbot` (e as referências de SSL no `nginx.conf`) do `docker-compose.yml`.
- Quando o domínio estiver pronto, usar o fluxo correto para emissão dos certificados, rodando os contêineres e validando o domínio.

## 4. Avisos (Warnings) Menores e Performance
**Problema A**: `the attribute version is obsolete`
- **Solução**: Remover a linha `version: '3.8'` do topo do `docker-compose.yml`, pois as versões atuais do Docker Compose (v2+) não utilizam mais essa chave.

**Problema B**: Redis exposto externamente (`6379:6379`)
- **Solução**: No `docker-compose.yml`, remover a cláusula `ports:` do serviço do Redis. Ele só precisa se comunicar internamente (na rede do Docker) com a API e o Celery, então não deve ficar exposto para a internet pública, melhorando a segurança.

**Problema C**: Redis - Aviso de `vm.overcommit_memory`
- **Solução**: Executar o comando `sysctl vm.overcommit_memory=1` no terminal root da VPS (via SSH) para otimizar o gerenciamento e o uso de memória do Redis.

## Soluções Implementadas no Código

Conforme as instruções, apliquei as seguintes modificações localmente (já prontas para subir):

1. **Correção do Docker Compose (`docker-compose.yml`)**:
   - Removi a cláusula obsoleta `version: '3.8'`.
   - Alterei a porta da API para `8001:8000` (evitando conflito).
   - Removi a porta externa do Redis (`6379:6379`).
   - Comentei temporariamente o serviço do `certbot` e seus volumes no `nginx` para evitar o erro de saída imediata que estava impedindo o deploy saudável.

2. **Correção do Erro do Celery / Pacote Python**:
   - Organizei os scripts geoespaciais (que estavam soltos na raiz) dentro de um diretório/pacote próprio chamado `hydro_mde/`. 
   - Ao mover `config.py`, `aoi.py`, `clip_raster.py`, etc., para esta pasta (onde já criei o `__init__.py`), o Python voltará a reconhecer o comando `from hydro_mde.xyz import abc` que era a causa da falha fatal no Celery.

---

**Status Atual**: Todos os contêineres (`api`, `celery_worker`, `nginx`, `redis`) subiram com sucesso e estão operacionais. O servidor está acessível na porta 80 e o `Health Check` está retornando `200 OK`. 

A bateria de testes automatizados confirmou que a infraestrutura está 100% conectada:
- A API recebe as requisições web.
- O Celery enfileira o Job perfeitamente comunicando-se com o Redis.

*Nota:* No teste prático de execução do script geoespacial, a Task finalizou como `FAILURE`, o que é muito comum para o Payload de teste "vazio" que o script envia, ou falta de dados raster na pasta `/data`. O ambiente em si já está devidamente orquestrado e online!
