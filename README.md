# Assistente SGP × Cariap

Cadastra os serviços do Cariap (livros digitais e demais planos do grupo TV) nos contratos
dos clientes de um provedor, pela interface web do SGP, sem acesso ao servidor.

Planos de internet e planos de serviço são cadastrados pela equipe responsável; o
assistente só **lê** o que existe. O trabalho dele é:

1. **mapear**: para cada plano de internet, quais serviços os clientes devem ter
   (por exemplo, 400_MEGA_FIBRA → E-book Super Essencial + Audiobook Super Duo).
   Planos com os mesmos serviços ficam num grupo;
2. **aplicar**: encontrar no SGP os clientes desses planos e cadastrar, contrato por
   contrato, os serviços que faltam, ativando cada um.

Um tour guiado (driver.js) explica cada etapa na primeira vez e pode ser reaberto pelo botão de ajuda.

## Instalar e abrir

Escolha **uma** das formas:

| Sistema | Executável pronto (nada para instalar) | Com Python 3.10+ |
|---|---|---|
| Windows | baixe `SGP-Cariap-windows.exe` e dê dois cliques | dois cliques em `iniciar.bat` |
| macOS | baixe `SGP-Cariap-macos-arm64` (Apple Silicon) ou `-x86_64` (Intel) | dois cliques em `iniciar.command` |
| Linux | baixe `SGP-Cariap-linux-x86_64`, `chmod +x` e execute | `./iniciar.sh` |
| Qualquer um | | `pip install .` e depois `sgp-cariap` (ou `python -m sgpcariap`) |

O assistente abre sozinho no navegador (`http://127.0.0.1:8765`). Para encerrar, feche a
janela do terminal que apareceu.

O assistente **não tem dependências**: usa só a biblioteca padrão do Python 3.10 ou mais novo. Os executáveis
saem dos Releases do repositório, gerados pelo GitHub Actions (veja abaixo).

**Primeira vez no macOS:** o executável não é assinado. Clique com o botão direito →
**Abrir** → **Abrir**, ou rode `xattr -d com.apple.quarantine SGP-Cariap-macos-*`.
**No Windows**, se o SmartScreen avisar, clique em *Mais informações → Executar assim mesmo*.

## Uso no dia a dia

1. **Provedor**: escolha ou crie o perfil no topo da barra lateral. Cada provedor guarda a
   própria URL, o mapeamento e os filtros neste navegador.
2. **Conexão**: URL do SGP, usuário e senha (de preferência um usuário dedicado). Logo após
   entrar, o assistente lê os planos de internet e os planos de serviço (grupo TV).
3. **Serviços**: à esquerda, os planos de internet com preço e clientes ativos;
   à direita, os planos de TV (serviços) cadastrados no SGP, com o gateway de cada um
   ("Só Cariap" já vem marcado quando o provedor tem esse gateway). Selecione planos
   de internet (clique na linha; a caixa do cabeçalho marca os visíveis) e marque à direita
   os serviços que os clientes deles devem receber. Uma caixa "parcial" indica que só parte
   dos selecionados tem aquele serviço. Planos com exatamente os mesmos serviços formam um
   grupo automaticamente (o nome dado ao grupo é mantido). "Copiar serviços de…" copia os
   serviços de outro plano. Planos com nome repetido no SGP ficam bloqueados até serem
   renomeados, porque o assistente não teria como distingui-los.
4. **Clientes**: por padrão, todos os contratos ativos dos planos mapeados; dá para restringir
   a alguns planos e POPs. **Buscar** mostra, para cada contrato, o que falta
   adicionar e o que falta ativar; quem já tem tudo é pulado. Com **Conferir cadastro**
   ligado (padrão), a busca também confere CPF/CNPJ, e-mail e celular com o 9 (sem ele o Cariap não cria o acesso) de cada cliente: quem
   tiver pendência aparece como **Revisar cadastro**, com o problema e um atalho para os
   contatos no SGP, e fica de fora até ser corrigido (basta buscar de novo). Desmarque quem não deve
   receber, defina um limite para o piloto e clique em **Iniciar**. Cada serviço entra no
   **contrato que já existe** (mesma fatura do plano de internet) e é ativado, o que cria o
   acesso no Cariap. Dá para pausar, retomar ou parar; rodar de novo só faz o que falta.
   Durante a execução, a barra mostra o percentual, o contrato e a etapa atuais, os
   concluídos e os erros e o tempo estimado. Ao final, as falhas aparecem agrupadas por causa,
   com o que fazer; **Tentar de novo** seleciona só os contratos que falharam, e o ícone de
   download gera um relatório `.csv` da lista.

**Exportar / Importar** salva e abre a configuração de um provedor em `.json`, sem a senha.

### Testar sem risco

- Ambiente de teste público: `https://demo.sgp.net.br`, usuário e senha `demo`. É compartilhado
  com outras pessoas, então use sempre um prefixo.
- **Prefixo de teste** (Padrões): tudo é criado como `PREFIXO Nome`, fácil de achar e apagar.
  Deixe vazio em produção.

## Segurança

- O servidor só escuta em `127.0.0.1` e recusa pedidos vindos de outros sites; a página
  não pode ser aberta dentro de outro site (CSP e `X-Frame-Options`).
- A **senha** fica apenas na memória do processo. Não é gravada em disco nem no navegador.
- Só uma execução por vez; enquanto ela roda, não dá para desconectar nem trocar de SGP.
- Gravações no SGP nunca são repetidas automaticamente: se a conexão cair no meio, o contrato
  fica com erro e a próxima busca mostra o que de fato ficou gravado.
- Cada execução gera um registro em `~/SGP-Cariap/execucoes/` (pasta trocável com a variável
  `SGP_CARIAP_DADOS`), gravado **durante** a execução: o `.json` com o retrato completo e o
  `.diario.jsonl` com uma linha por contrato concluído. Se o assistente for fechado no meio,
  o diário mostra o que já foi feito.
- **LGPD**: nos registros, CPF/CNPJ, telefone e e-mail do cliente vão mascarados
  (`***0001`, `f***@gmail.com`); os arquivos só podem ser lidos pelo usuário que roda o
  assistente; registros com mais de 90 dias são apagados ao iniciar uma execução
  (variável `SGP_CARIAP_RETENCAO_DIAS`; `0` guarda para sempre).
- SGP com certificado próprio ou autoassinado: marque *Aceitar certificado não verificado*
  na conexão (só nesse caso).
- Ao buscar clientes, o assistente confere se as telas do SGP têm os campos que ele usa. Se o
  SGP for de uma versão com telas diferentes, a busca para com a lista do que mudou, em vez de
  ler a base errado. A versão do SGP aparece ao passar o mouse sobre a conexão.

Mais detalhes para a equipe de TI (implantação, distribuição e assinatura dos executáveis) em
[docs/SEGURANCA.md](docs/SEGURANCA.md).

## Gerar os executáveis

Todos de uma vez, pelo GitHub: suba esta pasta num repositório e crie uma tag
(`git tag v0.5.0 && git push --tags`). O workflow `.github/workflows/build.yml` compila no
Windows, no macOS (Apple Silicon e Intel) e no Linux, testa cada executável e publica um
Release com os arquivos e o `SHA256SUMS.txt` para conferir o download. Também dá para rodar manualmente em *Actions → build → Run workflow*.

Só para o sistema atual, localmente:

```bash
pip install -r requirements-build.txt
python build.py          # saída em dist/
```

## Limites conhecidos

- A ativação real no Cariap depende do gateway Cariap configurado no plano de TV e dos dados
  do cliente (CPF válido, e-mail e celular com o 9). Plano de TV sem gateway: o SGP adiciona e
  marca o serviço como ativo, mas não envia nada ao Cariap. Quando não ativa, o contrato fica marcado com erro
  e volta como pendente na próxima busca.
- A lista de clientes vem do relatório "Contratos por serviço" do SGP; a ativação exige o
  contrato ativo (filtro padrão).
- No SGP, abrir os links de ação já executa a ação, sem confirmação (`ativar`, `desativar`,
  `delete`). O assistente só usa `ativar`.

## Para desenvolvedores

A organização do código, os padrões usados e o passo a passo para estender (mudança numa
tela do SGP, nova rota, nova tela) estão em
[docs/ARQUITETURA.md](docs/ARQUITETURA.md).

```bash
python -m sgpcariap --sem-navegador --detalhado      # roda a partir do código
python -m unittest discover -s tests -t . -v         # testes (sem rede)

pip install ".[dev]"                                 # ferramentas de qualidade (as mesmas do CI)
ruff check sgpcariap tests                           # estilo e erros comuns
mypy sgpcariap                                       # tipos
coverage run -m unittest discover -s tests -t . && coverage report --include='sgpcariap/*'
```

O CI recusa mudanças com erro no ruff ou no mypy, teste quebrado ou cobertura abaixo de 85%.
Histórico de versões em [CHANGELOG.md](CHANGELOG.md).

```
sgpcariap/
  dominio/     mapeamento de planos para serviços e opções de aplicação
  sgp/         sessão HTTP, formulários e telas do SGP
  cadastro/    leitura dos planos e aplicação nos clientes (lote)
  web/         API local, servidor e execuções em segundo plano
  static/      interface (módulos ES em js/), tour e exemplo
tests/         testes automatizados
app.py         atalho de inicialização (lançadores e PyInstaller)
build.py       gera o executável do sistema atual
```
