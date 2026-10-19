# Arquitetura

Guia para quem vai manter ou estender o assistente.

## Visão geral

O SGP não oferece API para cadastrar serviços em contratos nem consulta em massa de
clientes. O assistente usa a própria interface web: lê páginas e listagens, preenche os
formulários e envia, como um operador faria. Tudo roda num servidor local (só biblioteca
padrão do Python) que entrega uma página web e uma API JSON.

O assistente **não cadastra planos**. Ele lê os planos de internet e os planos de serviço
(grupo TV) existentes, guarda o mapeamento "plano de internet → serviços" e aplica esse
mapeamento nos contratos dos clientes, um por vez.

```
navegador ──► static/js (módulos ES) ──HTTP──► web ──► cadastro ──► sgp ──HTTPS──► SGP do provedor
                                                         │
                                                         └──► dominio
```

## Camadas

As dependências apontam sempre para baixo.

| Pacote | Responsabilidade | Não deve saber |
|---|---|---|
| `sgpcariap.dominio` | `Configuracao`: grupos de serviços (`GrupoServicos`), opções de aplicação (`ConfiguracaoLote`) e validação do mapeamento | que o SGP existe |
| `sgpcariap.sgp` | Sessão HTTP, leitura de formulários e as telas usadas (listagem de planos, relatório de contratos por serviço, serviço de TV do contrato) | o que é um grupo de serviços |
| `sgpcariap.cadastro` | Casos de uso: leitura dos planos (`CatalogoSGP`), montagem e execução do lote | HTTP da interface, threads |
| `sgpcariap.web` | API local, roteamento, servidor e execuções em segundo plano (pausar, retomar, parar) | nomes de campos do SGP |
| `sgpcariap/static` | Interface: estado, telas, combobox e tour | regras do SGP |

`sgpcariap.erros` é transversal: toda exceção esperada deriva de `ErroAssistente` e carrega
uma mensagem pronta para o usuário.

## Padrões de projeto e onde estão

| Padrão | Onde | Por quê |
|---|---|---|
| Page Object | `sgp/telas.py` (`TelaListaPlanos`, `TelaRelatorioServicos`, `TelaServicoTV`) | Rotas e nomes de campos do SGP ficam num só lugar |
| Command | `NovoServicoTV`, `FiltroServicos` | Pedido ao SGP como objeto, com os textos que o usuário vê |
| Facade | `ClienteSGP` (sessão autenticada), `AssistenteCadastro` (casos de uso) | Poucas operações, escondendo login, CSRF e leitura |
| Observer | `ObservadorExecucao` (implementado por `web.tarefas.Tarefa` e por dublês nos testes) | O executor informa o progresso sem conhecer a interface |
| Carga sob demanda com cache | `CatalogoSGP` (`cached_property`), descartado em `atualizar` | Reler o SGP só quando pedido |
| Registro por decorador | `@rota` em `web/api.py` | Uma rota nova é um método marcado |

No front-end, `Estado` (`EventTarget`) é a única fonte da verdade e publica eventos
(`alterada`, `recarregada`, `catalogo`, `planos`, `provedores`); cada tela assina o que lhe
interessa. `componentes/combobox.js` transforma qualquer `<input list>` em combobox.

Na tela de mapeamento, o vínculo é editado plano a plano (`servicosPorPlano` em
`dominio.js`) e os grupos são recalculados por `reagrupar`: planos com o mesmo conjunto de
serviços ficam no mesmo grupo, reaproveitando o nome que o grupo já tinha. Assim o arquivo
de configuração continua no formato `GrupoServicos` que o back-end espera. Planos de
internet ou de TV com nome repetido no SGP não podem ser vinculados, porque o relatório e o
formulário do SGP identificam o plano pelo nome.

## Fluxos

**Conectar e ler**: `ApiAssistente.conectar` → `ClienteSGP.conectar` (login com CSRF).
`/api/planos` devolve os planos de internet (preço, clientes ativos) e os de serviço (gateway).

**Montar o lote** (`cadastro/lote.py`, `MontadorLote`): consulta o relatório de contratos por
serviço duas vezes, uma para os serviços de internet dos planos mapeados (com filtros de POP e
status) e outra para os serviços de TV já existentes, e compara contrato a contrato: o que
falta adicionar e o que está inativo e falta ativar.

**Conferir o cadastro** (`cadastro/validacao.py`, `TelaListaClientes`): com
`ConfiguracaoLote.validar_cadastro` ligado (padrão), os contratos pendentes têm o cadastro
conferido antes da execução. Os contatos vêm da exportação em Excel da lista de clientes do SGP
(`/admin/cliente/list/?printexcel=true`, uma exportação por plano de internet), lida por
`sgp/planilha.py` só com a biblioteca padrão: uma consulta por plano em vez de uma por cliente.
A planilha traz colunas sensíveis (senha do PPPoE); só ID do cliente, contrato, CPF/CNPJ,
celulares, telefones e e-mails são lidos, e nada é gravado. `validar` gera `Pendencia`s: sem
e-mail ou e-mail inválido, nenhum celular com o 9 (DDD + 9 + 8 dígitos; o Cariap só cria o
acesso com ele), CPF/CNPJ ausente ou com dígito verificador errado bloqueiam
(`SituacaoItem.BLOQUEADO`, fora da execução). Sem celular, a pendência diz o motivo: sem
telefone, só telefone fixo, celular antigo sem o 9 (com o número sugerido) ou telefone
inválido. E-mail errado ao lado de um válido e contrato fora da exportação são avisos. Sem nenhum cliente no filtro, o SGP devolve a página da lista no lugar
da planilha: isso vale como lista vazia. Se a exportação de um plano falhar, os contratos dele
seguem com o aviso "Cadastro não conferido" e o motivo, sem interromper a busca.

**Nomes repetidos nos filtros**: o SGP aceita opções com o mesmo nome (o demo tem quatro POPs
"Natal-RN", cada um com um ID, e a ordem muda de uma tela para outra). Nos filtros de POP e
status, `ListaOpcoes.resolver_todos` envia todos os IDs com aquele nome, e o SGP soma os
resultados. Com `resolver`, o relatório e a exportação ficavam cada um com o *seu* primeiro ID,
e um contrato do relatório podia não aparecer na exportação. Na interface, cada nome aparece
uma vez só.

**Executar** (`ExecutorLote`): para cada contrato pendente, lê o endereço de instalação do
serviço de internet, adiciona cada serviço que falta (`TelaServicoTV.adicionar` devolve o ID
criado) e ativa. A cada passo, `ItemLote.etapa` diz o que está sendo feito ("Adicionando X
(1/2)", "Ativando X") e `ItemLote.duracao` guarda o tempo do contrato, usado na estimativa de
tempo restante. `ControleExecucao` atende pausar, retomar e parar (`/api/job/controle`). Cada
execução gera um JSON em `~/SGP-Cariap/execucoes/`.

**Falhas** (`cadastro/falhas.py`): cada erro vira uma `Falha` com causa (`Causa`), título e
orientação, a partir do tipo da exceção (`ErroPlanoIndisponivel`, `ErroAtivacao`,
`ErroFormulario`...). A falha de um serviço não impede os outros; a interface agrupa as falhas
por causa e permite reprocessar só os contratos que falharam. Causas *gerais* (SGP sem
resposta, sessão recusada, sem permissão) interrompem a execução depois de
`ExecutorLote.LIMITE_FALHAS_GERAIS` contratos seguidos, porque os próximos falhariam igual.

**Custo por serviço**: ler o formulário, gravar, listar os serviços do cliente (para achar o
ID novo) e ativar, conferindo o resultado na página que o próprio "ativar" devolve. A lista de
serviços do cliente é reaproveitada entre serviços do mesmo cliente. Cada página do SGP leva
perto de 1 s para ser gerada; por isso o número de requisições é o que mais pesa.

**Rede** (`sgp/http.py`, `sgp/cliente.py`): uma conexão aberta por sessão (keep-alive). Leituras
que falham por oscilação de rede ou 502/503/504 são repetidas com espera crescente
(`PoliticaRepeticao`); envios nunca são repetidos, para não gravar em dobro. Se a sessão expirar,
`ClienteSGP` entra de novo uma vez (a senha fica só na memória do objeto) e repete a operação.

**Atenção**: no SGP, abrir os links de ação já executa a ação, sem confirmação
(`/servicos/tv/<id>/ativar`, `/desativar` e `/delete/`). O assistente só acessa `ativar`;
nunca monte um GET para `delete`.

## Como estender

**O SGP mudou uma tela**: ajuste a classe correspondente em `sgp/telas.py` e a página de
exemplo em `tests/test_telas.py`. Cada tela lista em `CAMPOS` os campos de que depende;
`TelasSGP.incompatibilidades()` confere esses campos antes de cada busca e para com uma
mensagem clara quando o SGP é de outra versão. Quando um campo existir só em algumas versões,
consulte `formulario.tem_campo(...)` e tire-o de `CAMPOS`.

**Outro tipo de serviço** (por exemplo, planos "Outros" em vez de TV): acrescente em
`TelaRelatorioServicos` o filtro do tipo e, em `sgp/telas.py`, a tela de adicionar do tipo
(o SGP tem rotas equivalentes `clientecontrato/<id>/generico/add/`), e escolha a tela em
`ExecutorLote` conforme o grupo do serviço.

**Nova rota na API**: método em `ApiAssistente` decorado com `@rota(...)`, recebendo e
devolvendo `dict`. Lance `ErroAssistente` para erros que o usuário deve ver.

**Nova tela na interface**: classe em `static/js/telas/` derivando de `Tela`, instanciada em
`main.js`. Altere `this.config` e chame `this.estado.alterar()`.

## Convenções

- Nomes do domínio em português, como os usuários e o SGP os usam.
- Planos guardados como aparecem no SGP ("Fibra - 400_MEGA_FIBRA"); serviços pelo nome do plano de TV.
- Sem dependências externas em tempo de execução. `certifi` é opcional e entra só no executável.

## Garantias de operação

- **Gravação nunca repetida.** `SessaoHTTP` abre conexão nova para cada POST e não repete o
  envio se a conexão cair: não há como saber se o SGP gravou. A segurança vem da busca, que
  sempre relê o SGP; um serviço gravado e não identificado aparece como "ativar" na próxima.
  Leituras (GET) continuam com novas tentativas.
- **Uma execução por vez.** `GerenciadorTarefas.iniciar` confere e registra a tarefa sob a
  mesma trava; a API recusa desconectar ou conectar a outro SGP enquanto ela roda.
- **Registro durante a execução.** `RegistroExecucoes` grava o `.json` no início e no fim
  (troca atômica, com `os.replace`) e o `.diario.jsonl` a cada contrato e mensagem.
- **Dados pessoais.** `web/privacidade.py` mascara documento, telefone e e-mail em tudo o que
  vai para o disco; arquivos 0600, pasta 0700, retenção configurável (`Ambiente.retencao_dias`).
- **Página local.** CSP sem scripts de fora nem `eval`, `X-Frame-Options: DENY`, limite de
  5 MB por requisição, `Host`/`Origin` conferidos.

## Testes

```bash
python -m unittest discover -s tests -t . -v
```

Não acessam a rede externa: `tests/test_lote.py` usa um relatório e uma tela de serviço de TV
falsos; `test_http.py` imita o SGP num servidor local (conexão reaproveitada, cookies, novas
tentativas, POST nunca repetido, sessão expirada, versão do SGP); `test_telas.py` lê páginas
com a estrutura do SGP 1.0.251 (listagens, relatório paginado, adicionar e ativar serviço);
`test_tarefas.py` cobre execução única, registro em disco, máscara de dados e retenção;
`test_web.py` sobe o servidor real numa porta local (cabeçalhos de segurança, limite de corpo).

Qualidade: `ruff check sgpcariap tests`, `mypy sgpcariap` e cobertura mínima de 85%,
conferidos no CI (`.github/workflows/build.yml`).
