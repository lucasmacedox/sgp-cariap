# Assistente SGP × Cariap

Cadastra e ativa os serviços do Cariap (planos do grupo TV) nos contratos dos clientes de um
provedor, pela interface web do SGP. Não precisa de acesso ao servidor do SGP.

1. **Serviços**: define quais serviços os clientes de cada plano de internet devem ter.
2. **Clientes**: busca os contratos desses planos, mostra o que falta e aplica, contrato por
   contrato, no contrato existente (mesma fatura). Rodar de novo só faz o que falta.

## Instalação

| Sistema | Executável | Com Python 3.10+ |
|---|---|---|
| Windows | `SGP-Cariap-windows.exe` | `iniciar.bat` |
| macOS | `SGP-Cariap-macos-arm64` ou `-x86_64` | `iniciar.command` |
| Linux | `SGP-Cariap-linux-x86_64` | `./iniciar.sh` |

Sem dependências além da biblioteca padrão. O assistente abre em `http://127.0.0.1:8765`;
fechar o terminal encerra.

Os executáveis não são assinados: no macOS, botão direito → **Abrir**; no Windows, *Mais
informações → Executar assim mesmo*.

## Uso

1. **Conexão**: URL do SGP, usuário e senha. Use um usuário dedicado com acesso a planos,
   relatório de contratos por serviço, lista de clientes (exportação) e serviços de TV.
2. **Serviços**: selecione planos de internet à esquerda e marque os serviços à direita.
   Planos com os mesmos serviços formam um grupo.
3. **Clientes**: **Buscar** lista os contratos pendentes. Com *Conferir cadastro*, clientes
   sem CPF/CNPJ válido, e-mail ou celular com o 9 ficam de fora até serem corrigidos.
   Use **Limite** para um piloto e depois **Iniciar**. Dá para pausar e parar a qualquer momento.

**Exportar / Importar** salva a configuração do provedor em `.json`, sem a senha.

Para testar: `https://demo.sgp.net.br` (demo/demo). O ambiente é compartilhado; use só
clientes e planos criados para o teste.

## Funcionamento

- O servidor só escuta em `127.0.0.1` e recusa requisições de outras origens.
- A senha fica só em memória.
- Gravações no SGP nunca são repetidas automaticamente. Se a conexão cair, o contrato fica com
  erro e a próxima busca mostra o que foi gravado.
- Uma execução por vez. Cada execução fica registrada em `~/SGP-Cariap/execucoes/`
  (`SGP_CARIAP_DADOS` muda a pasta): `.json` com o resultado e `.diario.jsonl` com uma linha
  por contrato, gravada na hora.
- Antes de buscar, o assistente confere se as telas do SGP têm os campos esperados e para se
  a versão for diferente.
- No SGP, um GET em `/ativar`, `/desativar` ou `/delete/` executa a ação sem confirmação. O
  assistente só usa `ativar`.
- A ativação no Cariap depende do gateway Cariap no plano de TV. Sem gateway, o SGP marca o
  serviço como ativo, mas não envia nada ao Cariap.

## Desenvolvimento

```bash
python -m sgpcariap --sem-navegador --detalhado
python -m unittest discover -s tests -t .

pip install ".[dev]"
ruff check sgpcariap tests
mypy sgpcariap
```

```
sgpcariap/
  dominio/    configuração do provedor (mapeamento plano → serviços)
  sgp/        sessão HTTP, formulários e telas do SGP
  cadastro/   montagem e execução do lote, conferência de cadastro
  web/        servidor local, API e execuções em segundo plano
  static/     interface (módulos ES)
```

Se o SGP mudar uma tela, ajuste a classe em `sgp/telas.py` (e `CAMPOS`) e a página de exemplo
em `tests/test_telas.py`.

### Executáveis

Uma tag `v*` dispara o workflow `.github/workflows/build.yml`, que gera os executáveis de
Windows, macOS e Linux e publica um Release com `SHA256SUMS.txt`. Para gerar só o do sistema
atual:

```bash
pip install -r requirements-build.txt
python build.py
```
