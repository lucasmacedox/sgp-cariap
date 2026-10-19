"""Assistente SGP × Cariap.

Lê os planos já cadastrados no SGP de um provedor, guarda quais serviços (planos
do grupo TV, como os livros do Cariap) os clientes de cada plano de internet
devem ter e cadastra esses serviços nos contratos, um por um, pela interface web.

Organização em camadas (dependências sempre de cima para baixo):

    web        API local, servidor HTTP e execuções em segundo plano
    cadastro   casos de uso: leitura dos planos e aplicação nos clientes
    sgp        integração com a interface web do SGP
    dominio    mapeamento de planos para serviços e opções de aplicação
"""

__version__ = "0.5.0"
