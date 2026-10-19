# Histórico de versões

## 0.5.0 — 2026-10-19

Revisão para uso em operação.

### Segurança e confiabilidade
- Gravações no SGP (POST) usam conexão nova e nunca são repetidas automaticamente; antes, uma
  queda de conexão podia gravar o mesmo serviço duas vezes no contrato.
- Só uma execução por vez, garantido no servidor (duplo clique ou duas abas não iniciam duas).
- Não é possível desconectar nem trocar de SGP durante uma execução.
- Registro da execução gravado durante o trabalho (`.diario.jsonl`), não só no fim.
- LGPD: CPF/CNPJ, telefone e e-mail mascarados nos registros; arquivos só para o dono (0600);
  retenção de 90 dias (`SGP_CARIAP_RETENCAO_DIAS`).
- Página local com CSP, `X-Frame-Options: DENY`, `Referrer-Policy` e limite de 5 MB por requisição.
- CSV exportado protegido contra fórmulas (texto começando com `=`, `+`, `-`, `@`).

### Compatibilidade
- A versão do SGP é lida no login e mostrada na conexão e nos registros.
- Antes de cada busca, o assistente confere se as telas do SGP têm os campos que ele usa e
  para com uma mensagem clara se não tiverem.

### Cadastro
- Celular com o 9 obrigatório; só telefone fixo bloqueia o contrato.
- POPs e planos com nome repetido no SGP entram todos no filtro.

### Qualidade
- ruff e mypy sem pendências e obrigatórios no CI, com cobertura mínima de 85% (hoje 91%).
- Novos testes das telas do SGP, das execuções em segundo plano e dos cabeçalhos de segurança.
- Ações do GitHub fixadas por commit; Release com `SHA256SUMS.txt`.
- Documentação de segurança e implantação em `docs/SEGURANCA.md`.

## 0.4.0 e anteriores

Versões anteriores à revisão, sem histórico detalhado.
