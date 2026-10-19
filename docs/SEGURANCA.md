# Segurança e implantação

Para a equipe de TI que vai distribuir o assistente e para quem vai operá-lo nos provedores.

## O que o assistente faz no SGP

| Ação | Como | Reversível pela interface do SGP |
|---|---|---|
| Lê planos, relatório de contratos e lista de clientes | GET | — |
| Exporta a lista de clientes (Excel) | GET; usa só ID, contrato, CPF/CNPJ, celulares, telefones e e-mails. A coluna de senha é descartada e nada da planilha vai para o disco | — |
| Adiciona serviço de TV num contrato | POST no formulário "adicionar serviço" | sim, excluindo o serviço |
| Ativa o serviço de TV | GET em `/admin/servicos/tv/<id>/ativar` (é assim que o SGP faz) | sim, "Desativar" |

Nunca acessa `desativar` nem `delete`, nem cadastra ou altera planos e clientes.

## Usuário no SGP

Crie um usuário **dedicado** (por exemplo `cariap-assistente`) com acesso só a:

- planos (consulta);
- relatórios → contratos → serviços;
- clientes → lista (com exportação);
- contratos: adicionar e ativar serviços de TV.

Assim o histórico do SGP mostra o que foi feito pelo assistente, e a senha pode ser trocada
ao fim do trabalho num provedor.

## Dados e LGPD

| Dado | Onde fica | Por quanto tempo |
|---|---|---|
| Senha do SGP | só na memória do processo (para entrar de novo se a sessão expirar) | até fechar o assistente |
| Configuração do provedor (URL, usuário, mapeamento) | `localStorage` do navegador; exportável em `.json`, sem senha | até apagar o provedor |
| Registro da execução (`.json` e `.diario.jsonl`) | `~/SGP-Cariap/execucoes/` (ou `SGP_CARIAP_DADOS`), pasta 0700, arquivos 0600 | 90 dias (`SGP_CARIAP_RETENCAO_DIAS`) |
| Nome do cliente e número do contrato | no registro, para auditoria | idem |
| CPF/CNPJ, telefone e e-mail | no registro só mascarados (`***0001`, `f***@gmail.com`) | idem |
| Relatório `.csv` (botão de download) | onde o operador salvar; **sem máscara**, porque serve para corrigir cadastros | responsabilidade de quem baixou |

No Windows as permissões 0600/0700 não se aplicam; a pasta fica no perfil do usuário, que
já é protegido pelo sistema.

## Rede

- O servidor local escuta só em `127.0.0.1` (portas 8765 a 8784); nada é exposto na rede.
- Pedidos com `Host` ou `Origin` de outro endereço são recusados (protege contra sites
  maliciosos e DNS rebinding).
- A página tem CSP restritiva (só recursos próprios, sem `eval`) e não pode ser aberta
  dentro de outro site.
- A única conexão de saída é HTTPS para o SGP informado. O certificado é verificado, a não
  ser que o operador marque *Aceitar certificado não verificado* (só para SGP com
  certificado próprio, em rede interna).

## Distribuição dos executáveis

Os executáveis são gerados pelo GitHub Actions a cada tag `v*`, com as ações fixadas por
commit, e o Release traz `SHA256SUMS.txt`. Para conferir um download:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing          # Linux
shasum -a 256 SGP-Cariap-macos-arm64                  # macOS: compare com o arquivo
certutil -hashfile SGP-Cariap-windows.exe SHA256      # Windows: compare com o arquivo
```

**Assinatura digital (pendente, depende da empresa).** Sem assinatura, o SmartScreen do
Windows e o Gatekeeper do macOS mostram aviso. Para uso corporativo:

- **Windows**: certificado de assinatura de código (OV/EV) da empresa; no workflow, um
  passo `signtool sign /fd SHA256 /tr <timestamp> /td SHA256 dist/SGP-Cariap-windows.exe`
  com o certificado num *secret* do repositório.
- **macOS**: conta Apple Developer da empresa; `codesign --options runtime` com o
  certificado "Developer ID Application" e `xcrun notarytool submit --wait`.
- Alternativa sem certificado: distribuir pelo canal interno de software da empresa
  (Intune, JAMF etc.) ou usar a versão em Python (`iniciar.*`), que não passa por esses
  bloqueios.

## Piloto num provedor novo

1. Conecte com o usuário dedicado e confira a versão do SGP (passe o mouse sobre a conexão).
2. **Buscar** com *Conferir cadastro* ligado; corrija ou deixe de fora os pendentes.
3. Rode com **Limite** de 5 contratos e confira no SGP e no Cariap se o acesso foi criado.
4. Só então rode sem limite. Pausar e parar são seguros a qualquer momento; rodar de novo só
   faz o que falta.

## Problemas de segurança

Encontrou uma falha? Não abra issue pública: avise diretamente os mantenedores do
repositório.
