// Etapa 1: conexão com o SGP do provedor atual.

import { Eventos } from '../estado.js';
import { $, $$, ocupado, status } from '../util.js';
import { Tela } from './base.js';

export class TelaConexao extends Tela {
  constructor(contexto) {
    super(contexto);
    this.mensagem = $('#cx-msg');
    $('#form-conexao').addEventListener('submit', (evento) => {
      evento.preventDefault();
      this.conectar();
    });
    $('#btn-recarregar').addEventListener('click', () => this.recarregar());
    $('#btn-desconectar').addEventListener('click', () => this.desconectar());
    this.quando([Eventos.RECARREGADA], () => this.preencherCampos());
    this.quando([Eventos.CATALOGO], () => this.renderizarConexao());
    this.quando([Eventos.PLANOS], () => this.renderizarPlanos());
    this.preencherCampos();
  }

  preencherCampos() {
    const { sgp } = this.config;
    $('#cx-url').value = sgp.url || '';
    $('#cx-usuario').value = sgp.usuario || '';
    $('#cx-ssl').checked = Boolean(sgp.ignorar_ssl);
    $('#cx-senha').value = '';
  }

  async conectar() {
    const botao = $('#btn-conectar');
    const dados = {
      url: $('#cx-url').value.trim(),
      usuario: $('#cx-usuario').value.trim(),
      senha: $('#cx-senha').value,
      ignorar_ssl: $('#cx-ssl').checked,
    };
    const restaurar = ocupado(botao, 'Conectando…');
    status(this.mensagem, '');
    try {
      const resposta = await this.api.conectar(dados);
      $('#cx-senha').value = '';
      this.config.sgp = { url: resposta.url, usuario: dados.usuario, ignorar_ssl: dados.ignorar_ssl };
      $('#cx-url').value = resposta.url;
      this.estado.alterar();
      this.estado.definirConexao(resposta);
      await this.lerPlanos();
      status(this.mensagem, 'Conectado', 'ok');
    } catch (erro) {
      status(this.mensagem, erro.message, 'erro');
    } finally {
      restaurar();
    }
  }

  async lerPlanos(reler = false) {
    this.estado.definirPlanos(await this.api.planos(reler));
  }

  async recarregar() {
    const restaurar = ocupado($('#btn-recarregar'), 'Atualizando…');
    try {
      await this.lerPlanos(true);
      this.avisos.mostrar('Planos atualizados');
    } catch (erro) {
      this.avisos.erro(erro.message);
    } finally {
      restaurar();
    }
  }

  async desconectar() {
    try {
      await this.api.desconectar();
    } catch (erro) {
      // com uma execução em andamento o servidor recusa; a conexão continua valendo
      if (!erro.message.startsWith('O assistente não responde')) {
        this.avisos.erro(erro.message);
        return;
      }
    }
    this.estado.definirConexao(null);
    status(this.mensagem, '');
  }

  renderizarConexao() {
    const { conexao } = this.estado;
    const indicador = $('.conexao-estado');
    const texto = $('#pill-conexao');
    $('#cx-resumo').hidden = !conexao;
    indicador.dataset.estado = conexao ? 'on' : 'off';
    if (!conexao) {
      texto.textContent = 'Desconectado';
      delete indicador.dataset.dica;
      return;
    }
    texto.textContent = `${conexao.usuario} @ ${conexao.url.replace(/^https?:\/\//, '')}`;
    indicador.dataset.dica = conexao.versao_sgp ? `${conexao.url} · SGP versão ${conexao.versao_sgp}` : conexao.url;
  }

  renderizarPlanos() {
    const planos = this.estado.planos;
    if (!planos) return;
    const valores = {
      planos_internet: planos.planos_internet.length,
      com_clientes: planos.planos_internet.filter((p) => p.ativos > 0).length,
      planos_servico: planos.planos_servico.length,
    };
    for (const campo of $$('[data-r]')) campo.textContent = valores[campo.dataset.r];
  }
}
