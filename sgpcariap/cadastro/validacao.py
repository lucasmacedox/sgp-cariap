"""Conferência do cadastro antes de aplicar: o Cariap cria o acesso com e-mail, celular e CPF/CNPJ do SGP."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..sgp import ContatosCliente

ORIENTACAO = "Corrija no SGP (cliente → Contatos ou Cadastro) e busque de novo."

_EMAIL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
                    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}")
# "gmail.con"
_FINAIS_ERRADOS = {"con", "cmo", "cpm", "comm", "coom", "vom", "xom", "cim"}


@dataclass(frozen=True)
class Pendencia:
    codigo: str
    titulo: str
    detalhe: str = ""
    bloqueia: bool = True

    def para_dict(self) -> dict:
        return {"codigo": self.codigo, "titulo": self.titulo, "detalhe": self.detalhe,
                "bloqueia": self.bloqueia, "orientacao": ORIENTACAO}


NAO_ENCONTRADO = "o contrato não apareceu na lista de clientes do SGP"


def validar(contatos: ContatosCliente | None, motivo: str = NAO_ENCONTRADO) -> list[Pendencia]:
    if contatos is None:
        return [Pendencia("nao_conferido", "Cadastro não conferido", motivo, bloqueia=False)]
    return [*_documento(contatos.documento), *_emails(contatos.emails),
            *_telefones(contatos.celulares + contatos.telefones)]


def email_valido(email: str) -> bool:
    email = email.strip()
    return bool(_EMAIL.fullmatch(email)) and email.rsplit(".", 1)[-1].lower() not in _FINAIS_ERRADOS


def _emails(emails: tuple[str, ...]) -> list[Pendencia]:
    if not emails:
        return [Pendencia("sem_email", "Sem e-mail")]
    invalidos = [e for e in emails if not email_valido(e)]
    if len(invalidos) == len(emails):
        return [Pendencia("email_invalido", "E-mail inválido", ", ".join(invalidos))]
    if invalidos:
        return [Pendencia("email_invalido", "E-mail com erro", ", ".join(invalidos) + " (há outro válido)",
                          bloqueia=False)]
    return []


def _digitos(numero: str) -> str:
    """DDD + número, sem o 55; vazio se não for um telefone válido."""
    digitos = re.sub(r"\D", "", numero).lstrip("0")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11) or "0" in digitos[:2] or len(set(digitos[2:])) == 1:
        return ""
    return digitos


def tipo_telefone(numero: str) -> str | None:
    """"celular", "fixo" ou ``None``."""
    digitos = _digitos(numero)
    if len(digitos) == 11:
        return "celular" if digitos[2] == "9" else None
    return "fixo" if digitos and digitos[2] in "2345" else None  # 6-9 com 10 dígitos: celular sem o 9


def celular_sem_nove(numero: str) -> str | None:
    """"(84) 9999-0001" → "(84) 99999-0001"."""
    digitos = _digitos(numero)
    if len(digitos) != 10 or digitos[2] not in "6789":
        return None
    return f"({digitos[:2]}) 9{digitos[2:6]}-{digitos[6:]}"


def _telefones(numeros: tuple[str, ...]) -> list[Pendencia]:
    # o Cariap só cria o acesso com celular com o 9
    if not numeros:
        return [Pendencia("sem_telefone", "Sem telefone")]
    tipos = {tipo_telefone(n) for n in numeros}
    if "celular" in tipos:
        return []
    antigos = [(n, celular_sem_nove(n)) for n in numeros if celular_sem_nove(n)]
    if antigos:
        return [Pendencia("celular_sem_9", "Celular sem o 9", ", ".join(f"{n} → {novo}" for n, novo in antigos))]
    if "fixo" in tipos:
        return [Pendencia("sem_celular", "Sem celular", "só telefone fixo: " + ", ".join(numeros))]
    return [Pendencia("telefone_invalido", "Telefone inválido", ", ".join(numeros))]


def documento_valido(documento: str) -> bool:
    digitos = re.sub(r"\D", "", documento)
    if len(set(digitos)) == 1:
        return False
    if len(digitos) == 11:
        return _digitos_conferem(digitos, 9, range(10, 1, -1)) and _digitos_conferem(digitos, 10, range(11, 1, -1))
    if len(digitos) == 14:
        pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        return _digitos_conferem(digitos, 12, pesos, cnpj=True) and _digitos_conferem(digitos, 13, [6] + pesos, cnpj=True)
    return False


def _digitos_conferem(digitos: str, posicao: int, pesos, *, cnpj: bool = False) -> bool:
    soma = sum(int(d) * p for d, p in zip(digitos[:posicao], pesos))
    resto = soma % 11
    if cnpj:
        esperado = 0 if resto < 2 else 11 - resto
    else:
        esperado = (soma * 10 % 11) % 10
    return int(digitos[posicao]) == esperado


def _documento(documento: str) -> list[Pendencia]:
    if not documento.strip():
        return [Pendencia("documento_invalido", "Sem CPF/CNPJ")]
    if not documento_valido(documento):
        return [Pendencia("documento_invalido", "CPF/CNPJ inválido", documento)]
    return []
