import { Eventos } from '../estado.js';
import { $, $$, alternar, baixar, duracao, esc, info, numeroOuVazio, ocupado, plural, preencherLista, slug, status } from '../util.js';
import { Tela } from './base.js';

const SITUACOES = {
  pendente: ['', 'Pendente'],
  completo: ['', 'Completo'],
  rodando: ['rodando', 'Processando'],
  concluido: ['ok', 'Concluído'],
  erro: ['erro', 'Erro'],
  pulado: ['', 'Fora'],
  bloqueado: ['aviso', 'Revisar cadastro'],
};
const TITULOS_PENDENCIA = {
  sem_email: 'Sem e-mail', email_invalido: 'E-mail inválido', sem_telefone: 'Sem telefone',
  telefone_invalido: 'Telefone inválido', sem_celular: 'Sem celular (só fixo)', celular_sem_9: 'Celular sem o 9',
  documento_invalido: 'CPF/CNPJ ausente ou inválido',
  nao_conferido: 'Cadastro não conferido',
};
const PALAVRA = 'INICIAR';
const INTERVALO_CONSULTA_MS = 1000;

export class TelaLote extends Tela {
  constructor(contexto) {
    super(contexto);
    this.itens = [];
    this.selecionados = new Set();
    this.tarefa = null;
    this.causaVisivel = '';
    this.pendenciaVisivel = '';
    this.mensagem = $('#lt-msg');
    this.corpo = $('#tb-lote tbody');

    $('#btn-lote-buscar').addEventListener('click', () => this.buscar());
    $('#btn-lote-iniciar').addEventListener('click', () => this.pedirConfirmacao());
    $('#btn-lote-pausar').addEventListener('click', () => this.#controlar(this.tarefa?.pausado ? 'retomar' : 'pausar'));
    $('#btn-lote-parar').addEventListener('click', () => this.#controlar('parar'));
    $('#lt-filtro').addEventListener('input', () => this.#renderizarTabela());
    $('#lt-ver').addEventListener('change', (e) => this.#filtrarTabela({ ver: e.target.value }));
    $('#lt-marcar').addEventListener('click', () => this.#selecionarPendentes(true));
    $('#lt-desmarcar').addEventListener('click', () => this.#selecionarPendentes(false));
    $('#lt-csv').addEventListener('click', () => this.#baixarCsv());
    $('#btn-lote-retentar').addEventListener('click', () => this.#retentar());
    $('#lt-falhas-lista').addEventListener('click', (e) => {
      const botao = e.target.closest('[data-ver-causa]');
      if (botao) this.#filtrarTabela({ ver: 'erro', causa: botao.dataset.verCausa, rolar: true });
    });
    $('#lt-cadastros-lista').addEventListener('click', (e) => {
      const botao = e.target.closest('[data-ver-pendencia]');
      if (botao) this.#filtrarTabela({ pendencia: botao.dataset.verPendencia, rolar: true });
    });
    this.corpo.addEventListener('change', (e) => this.#alternarLinha(e.target));
    const secao = $('#sec-lote');
    secao.addEventListener('input', (e) => this.#editar(e.target));
    secao.addEventListener('change', (e) => this.#confirmar(e.target));
    secao.addEventListener('click', (e) => this.#removerEtiqueta(e.target.closest('[data-lt-remover]')));
    $('#lote-conf-palavra').addEventListener('input', (e) => {
      $('#lote-conf-ok').disabled = e.target.value.trim().toUpperCase() !== PALAVRA;
    });
    $('#dlg-lote').addEventListener('close', () => { if ($('#dlg-lote').returnValue === 'ok') this.iniciar(); });

    this.quando([Eventos.CATALOGO], () => this.carregarOpcoes());
    this.quando([Eventos.RECARREGADA], () => { this.renderizar(); this.#limparLista(); });
    this.quando([Eventos.ALTERADA, Eventos.RECARREGADA], () => this.#listarPlanosMapeados());
    this.opcoes = { status: ['Ativo'] };
    this.renderizar();
  }

  get lote() {
    return this.config.lote;
  }

  #listarPlanosMapeados() {
    preencherLista('dl-lt-planos', this.config.grupos.flatMap((g) => g.planos));
  }

  async carregarOpcoes() {
    if (!this.estado.conectado) return;
    try {
      this.opcoes = await this.api.loteOpcoes();
      preencherLista('dl-lt-pops', this.opcoes.pops);
      this.#listarPlanosMapeados();
      this.renderizar();
    } catch (erro) {
      this.avisos.erro(`Filtros indisponíveis (${erro.message})`);
    }
  }

  renderizar() {
    for (const lista of ['planos', 'pops']) {
      $(`[data-lt-lista="${lista}"]`).innerHTML = this.lote[lista].map((valor, i) =>
        `<span class="etiqueta">${esc(valor)}<button type="button" data-lt-remover="${lista}" data-i="${i}" aria-label="Remover">×</button></span>`).join('');
    }
    $('#lt-status').innerHTML = (this.opcoes.status || ['Ativo']).map((s) => {
      const marcado = this.lote.status_contrato.includes(s);
      return `<label class="opcao-livro ${marcado ? 'marcado' : ''}"><input type="checkbox" data-lt-status="${esc(s)}" ${marcado ? 'checked' : ''}>${esc(s)}</label>`;
    }).join('');
    for (const campo of $$('[data-lt]')) {
      const valor = this.lote[campo.dataset.lt];
      if (campo.type === 'checkbox') campo.checked = Boolean(valor);
      else campo.value = valor ?? '';
    }
  }

  #editar(campo) {
    const chave = campo.dataset.lt;
    if (!chave) return;
    this.lote[chave] = campo.type === 'checkbox' ? campo.checked
      : ['pausa_segundos', 'limite'].includes(chave) ? numeroOuVazio(campo.value) : campo.value;
    this.estado.alterar();
    if (chave === 'validar_cadastro') this.#limparLista();  // a lista muda: quem estava fora pode entrar
  }

  #confirmar(campo) {
    if (campo.dataset.ltAdd !== undefined && campo.value.trim()) {
      const lista = this.lote[campo.dataset.ltAdd];
      if (!lista.includes(campo.value.trim())) lista.push(campo.value.trim());
      campo.value = '';
      this.#mudouFiltro();
    } else if (campo.dataset.ltStatus !== undefined) {
      const status = campo.dataset.ltStatus;
      this.lote.status_contrato = campo.checked
        ? [...this.lote.status_contrato, status] : this.lote.status_contrato.filter((s) => s !== status);
      this.#mudouFiltro();
    }
  }

  #removerEtiqueta(botao) {
    if (!botao) return;
    this.lote[botao.dataset.ltRemover].splice(Number(botao.dataset.i), 1);
    this.#mudouFiltro();
  }

  #mudouFiltro() {
    this.estado.alterar();
    this.renderizar();
    this.#limparLista();
  }

  #limparLista() {
    if (this.tarefa?.status === 'rodando') return;
    this.itens = [];
    for (const id of ['#lt-tabela-wrap', '#lt-resumo', '#lt-falhas', '#lt-cadastros']) $(id).hidden = true;
    $('#btn-lote-iniciar').disabled = true;
  }

  async buscar() {
    if (!this.estado.conectado) {
      status(this.mensagem, 'Conecte ao SGP primeiro', 'erro');
      return;
    }
    const restaurar = ocupado($('#btn-lote-buscar'), 'Buscando…');
    delete this.mensagem.dataset.dica;
    // o relatório do SGP demora em bases grandes
    const inicio = Date.now();
    const relogio = setInterval(() => status(this.mensagem, `Consultando o SGP… ${duracao((Date.now() - inicio) / 1000)}`), 1000);
    status(this.mensagem, 'Consultando o SGP…');
    $('#lt-falhas').hidden = true;
    try {
      const { itens } = await this.api.loteMontar(this.config);
      this.itens = itens;
      this.selecionados = this.#pendentes();
      $('#lt-tabela-wrap').hidden = false;
      const pendentes = this.selecionados.size;
      const revisar = this.#contar('bloqueado');
      const semConferir = itens.filter((i) => (i.pendencias || []).some((p) => p.codigo === 'nao_conferido')).length;
      const partes = [plural(itens.length, 'contrato', 'contratos'),
        pendentes ? plural(pendentes, 'pendente', 'pendentes') : (revisar ? '' : 'todos completos'),
        revisar ? `${revisar} com cadastro a revisar` : '',
        semConferir ? `${semConferir} sem conferir` : ''].filter(Boolean);
      status(this.mensagem, itens.length ? partes.join(' · ') : 'Nenhum contrato encontrado', itens.length ? '' : 'erro');
      this.#renderizarTabela();
      this.#renderizarCadastros();
      return itens;
    } catch (erro) {
      status(this.mensagem, erro.message, 'erro');
      return null;
    } finally {
      clearInterval(relogio);
      restaurar();
    }
  }

  #contar(situacao) {
    return this.itens.filter((i) => i.situacao === situacao).length;
  }

  #pendentes(filtro = () => true) {
    return new Set(this.itens.filter((i) => i.situacao === 'pendente' && filtro(i)).map((i) => i.contrato));
  }

  #filtrarTabela({ ver = '', causa = '', pendencia = '', rolar = false }) {
    $('#lt-ver').value = ver;
    if (rolar) $('#lt-filtro').value = '';
    this.causaVisivel = causa;
    this.pendenciaVisivel = pendencia;
    this.#renderizarTabela();
    if (rolar) $('#lt-tabela-wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  #visiveis() {
    const termo = $('#lt-filtro').value.trim().toLowerCase();
    const ver = $('#lt-ver').value;
    return this.itens.filter((i) => (!ver || i.situacao === ver)
      && (!this.causaVisivel || (i.falhas || []).some((f) => f.causa === this.causaVisivel))
      && (!this.pendenciaVisivel || (i.pendencias || []).some((p) => p.codigo === this.pendenciaVisivel))
      && (!termo || `${i.contrato} ${i.cliente} ${i.plano_internet}`.toLowerCase().includes(termo)));
  }

  #renderizarTabela() {
    const rodando = this.tarefa?.status === 'rodando';
    this.corpo.innerHTML = this.#visiveis().map((item) => {
      const [classe, texto] = SITUACOES[item.situacao] || ['', item.situacao];
      const escolhivel = item.situacao === 'pendente' && !rodando && !this.tarefa;
      return `<tr class="${item.situacao === 'rodando' ? 'rodando' : ''}">
        <td class="caixa">${escolhivel ? `<input type="checkbox" data-contrato="${esc(item.contrato)}" ${this.selecionados.has(item.contrato) ? 'checked' : ''} aria-label="Incluir contrato ${esc(item.contrato)}">` : ''}</td>
        <td class="contrato" data-th="Contrato">${esc(item.contrato)}</td><td class="cliente">${esc(item.cliente)}</td><td data-th="Plano">${esc(item.plano_internet)}</td>
        <td class="lista-detalhes" data-th="O que falta">${this.#falta(item)}</td>
        <td class="situacao">${this.#situacao(item, classe, texto)}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="6" class="vazio">Nenhum contrato.</td></tr>';
    this.#renderizarResumo();
  }

  #situacao(item, classe, texto) {
    const selo = `<span class="estado ${classe}">${texto}</span>`;
    if (item.situacao === 'rodando') return `${selo}<div class="nota">${esc(item.etapa || '')}</div>`;
    if (item.situacao === 'erro' && item.falhas?.length) {
      return selo + item.falhas.map((f) => `<div class="mensagem-erro"><b>${esc(f.titulo)}</b>${f.servico ? ` · ${esc(f.servico)}` : ''} ${info(`${f.orientacao} Detalhe: ${f.mensagem}`)}</div>`).join('');
    }
    if (item.pendencias?.length && ['bloqueado', 'pendente'].includes(item.situacao)) {
      return selo + this.#pendencias(item);
    }
    if (item.msg && ['erro', 'concluido'].includes(item.situacao)) {
      return `${selo}<div class="${item.situacao === 'erro' ? 'mensagem-erro' : 'nota'}">${esc(item.msg)}</div>`;
    }
    return selo;
  }

  #pendencias(item) {
    const linhas = item.pendencias.map((p) => `<span class="${p.bloqueia ? 'bloqueia' : 'alerta'}">${esc(p.titulo)}${p.detalhe ? ` · ${esc(p.detalhe)}` : ''}</span>`);
    const sgp = this.estado.conexao?.url;
    if (sgp && item.cliente_id && item.situacao === 'bloqueado') {
      linhas.push(`<a href="${esc(`${sgp}/admin/contato/list/cliente/${encodeURIComponent(item.cliente_id)}/`)}" target="_blank" rel="noopener">Abrir contatos no SGP ↗</a>`);
    }
    return `<div class="pendencias">${linhas.join('')}</div>`;
  }

  #falta(item) {
    const partes = [];
    if (item.faltando.length) partes.push(`Adicionar ${esc(item.faltando.join(', '))}`);
    if (item.ativar.length) partes.push(`Ativar ${esc(item.ativar.join(', '))}`);
    return partes.join('<br>') || '<span class="sutil">—</span>';
  }

  #renderizarResumo() {
    $('#lt-resumo').hidden = this.itens.length === 0;
    for (const campo of $$('[data-lt-n]')) {
      const chave = campo.dataset.ltN;
      campo.textContent = chave === 'selecionados' ? this.selecionados.size : this.#contar(chave);
    }
    $('#btn-lote-iniciar').disabled = this.selecionados.size === 0 || this.tarefa?.status === 'rodando';
  }

  #alternarLinha(campo) {
    const contrato = campo.dataset.contrato;
    if (!contrato) return;
    alternar(this.selecionados, contrato, campo.checked);
    this.#renderizarResumo();
  }

  #selecionarPendentes(marcar) {
    for (const item of this.#visiveis()) {
      if (item.situacao === 'pendente') alternar(this.selecionados, item.contrato, marcar);
    }
    this.#renderizarTabela();
  }

  pedirConfirmacao() {
    const total = this.selecionados.size;
    const limite = this.lote.limite ? Math.min(this.lote.limite, total) : total;
    const acao = this.lote.ativar ? 'adicionados e ativados' : 'adicionados, sem ativar';
    const sgp = (this.estado.conexao?.url || '').replace(/^https?:\/\//, '');
    $('#lote-conf-texto').innerHTML = `<b>${plural(limite, 'contrato', 'contratos')}</b> em ${esc(sgp)}. `
      + `Os serviços serão ${acao}, um contrato por vez. Dá para pausar a qualquer momento.`;
    $('#lote-conf-palavra').value = '';
    $('#lote-conf-ok').disabled = true;
    $('#dlg-lote').showModal();
  }

  async iniciar() {
    $('#btn-lote-iniciar').disabled = true;
    $('#btn-lote-buscar').disabled = true;
    $('#lt-falhas').hidden = true;
    delete this.mensagem.dataset.dica;
    status(this.mensagem, '');
    try {
      const { job } = await this.api.loteIniciar(this.config, [...this.selecionados]);
      await this.#acompanhar(job);
    } catch (erro) {
      status(this.mensagem, erro.message, 'erro');
    } finally {
      $('#btn-lote-buscar').disabled = false;
    }
  }

  async #acompanhar(id) {
    $('#lt-andamento').hidden = false;
    $('#lt-log-wrap').hidden = false;
    this.inicioExecucao = Date.now();
    let falhasSeguidas = 0;
    for (;;) {
      try {
        this.tarefa = await this.api.tarefa(id);
        falhasSeguidas = 0;
      } catch (erro) {
        // o assistente pode demorar a responder num pico
        if (++falhasSeguidas >= 5) throw erro;
        await new Promise((resolver) => setTimeout(resolver, INTERVALO_CONSULTA_MS * 2));
        continue;
      }
      this.itens = this.tarefa.passos;
      this.#renderizarTabela();
      this.#renderizarAndamento();
      if (this.tarefa.status !== 'rodando') break;
      await new Promise((resolver) => setTimeout(resolver, INTERVALO_CONSULTA_MS));
    }
    const erros = this.#contar('erro');
    const resumo = [plural(this.#contar('concluido'), 'concluído', 'concluídos'), plural(erros, 'erro', 'erros'),
      plural(this.#contar('pendente'), 'pendente', 'pendentes')].join(' · ');
    const tempo = duracao((Date.now() - this.inicioExecucao) / 1000);
    status(this.mensagem, `${resumo} · ${tempo}`, erros ? 'erro' : 'ok');
    this.mensagem.dataset.dica = `Registro salvo em ${this.tarefa.arquivo || 'execucoes/'}`;
    this.selecionados = this.#pendentes();
    this.tarefa = null;
    $('#lt-andamento').hidden = true;
    this.#renderizarTabela();
    this.#renderizarFalhas();
    this.#renderizarCadastros();
  }

  #alvo(t) {
    const alvo = t.passos.filter((p) => !['completo', 'pulado'].includes(p.situacao));
    return t.limite ? alvo.slice(0, t.limite) : alvo;  // o executor segue a ordem da lista
  }

  #renderizarAndamento() {
    const t = this.tarefa;
    const alvo = this.#alvo(t);
    const ok = alvo.filter((p) => p.situacao === 'concluido').length;
    const erros = alvo.filter((p) => p.situacao === 'erro').length;
    const feitos = ok + erros;
    const total = alvo.length || 1;
    const pct = Math.round((feitos / total) * 100);
    $('#lt-pct').textContent = `${pct}%`;
    $('#lt-contagem').textContent = `${feitos} de ${alvo.length}`;
    const barra = $('#lt-andamento .progresso');
    barra.setAttribute('aria-valuenow', String(pct));
    $('.feito', barra).style.width = `${(ok / total) * 100}%`;
    $('.falhou', barra).style.width = `${(erros / total) * 100}%`;
    $('#lt-n-ok').textContent = plural(ok, 'concluído', 'concluídos');
    $('#lt-n-erro').textContent = plural(erros, 'erro', 'erros');
    $('#lt-n-erro').hidden = erros === 0;

    const decorrido = (Date.now() - this.inicioExecucao) / 1000;
    $('#lt-decorrido').textContent = duracao(decorrido);
    // média dos contratos já processados mais a pausa
    const tempos = alvo.map((p) => p.duracao).filter((d) => typeof d === 'number');
    const restantes = alvo.length - feitos;
    let restante = '';
    if (restantes && !t.parada_pedida && !t.pausado) {
      const media = tempos.reduce((a, b) => a + b, 0) / tempos.length + (t.pausa_segundos || 0);
      restante = tempos.length ? ` · faltam ~${duracao(media * restantes)}` : ' · estimando…';
    }
    $('#lt-restante').textContent = restante;

    const atual = t.passos.find((p) => p.situacao === 'rodando');
    $('#lt-atual').innerHTML = t.parada_pedida ? '<span class="estado rodando">Parando após o contrato atual…</span>'
      : t.pausado ? '<span class="estado aviso">Pausado</span>'
        : atual ? `<span class="estado rodando">${esc(atual.cliente)}</span> <span class="nota">${esc(atual.etapa || '')}</span>`
          : '';
    $('#btn-lote-pausar').textContent = t.pausado ? 'Retomar' : 'Pausar';
    this.#renderizarRegistro(t.log);
    if (erros) this.#renderizarFalhas();
  }

  #renderizarRegistro(log) {
    const lista = $('#lt-log');
    const noFim = lista.scrollTop + lista.clientHeight >= lista.scrollHeight - 4;
    lista.replaceChildren(...log.map((l) => {
      const li = document.createElement('li');
      li.className = `nivel-${l.nivel}`; // prefixo: "info" colidia com o botão ⓘ (.info)
      const hora = document.createElement('time');
      const msg = document.createElement('span');
      hora.textContent = l.t;
      msg.textContent = l.msg;
      li.append(hora, msg);
      return li;
    }));
    if (noFim) lista.scrollTop = lista.scrollHeight;
  }

  #renderizarFalhas() {
    const grupos = new Map();
    for (const item of this.itens.filter((i) => i.situacao === 'erro')) {
      for (const f of item.falhas?.length ? item.falhas : [{ causa: 'outra', titulo: 'Erro', orientacao: item.msg }]) {
        const g = grupos.get(f.causa) ?? { ...f, contratos: new Set() };
        g.contratos.add(item.contrato);
        grupos.set(f.causa, g);
      }
    }
    $('#lt-falhas').hidden = grupos.size === 0;
    $('#btn-lote-retentar').hidden = Boolean(this.tarefa);
    $('#lt-falhas-lista').innerHTML = [...grupos.values()].sort((a, b) => b.contratos.size - a.contratos.size).map((g) => `
      <li>
        <span class="falha-n">${g.contratos.size}</span>
        <div><b>${esc(g.titulo)}</b><p class="nota">${esc(g.orientacao)}</p></div>
        <button class="btn sutil pequeno" type="button" data-ver-causa="${esc(g.causa)}">Ver</button>
      </li>`).join('');
  }

  #renderizarCadastros() {
    const grupos = new Map();
    for (const item of this.itens.filter((i) => ['bloqueado', 'pendente'].includes(i.situacao))) {
      for (const p of item.pendencias || []) {
        const g = grupos.get(p.codigo) ?? { ...p, bloqueia: false, contratos: new Set() };
        g.bloqueia ||= p.bloqueia;
        g.contratos.add(item.contrato);
        grupos.set(p.codigo, g);
      }
    }
    $('#lt-cadastros').hidden = grupos.size === 0;
    $('#lt-cadastros-lista').innerHTML = [...grupos.values()]
      .sort((a, b) => (b.bloqueia - a.bloqueia) || (b.contratos.size - a.contratos.size)).map((g) => `
      <li class="${g.bloqueia ? '' : 'so-aviso'}">
        <span class="falha-n">${g.contratos.size}</span>
        <div><b>${esc((g.bloqueia && TITULOS_PENDENCIA[g.codigo]) || g.titulo)}</b><p class="nota">${g.bloqueia ? 'Fica de fora até corrigir' : 'Só aviso, segue na lista'}</p></div>
        <button class="btn sutil pequeno" type="button" data-ver-pendencia="${esc(g.codigo)}">Ver</button>
      </li>`).join('');
  }

  async #retentar() {
    const comErro = new Set(this.itens.filter((i) => i.situacao === 'erro').map((i) => i.contrato));
    if (!(await this.buscar())) return;
    this.selecionados = this.#pendentes((i) => comErro.has(i.contrato));
    $('#lt-ver').value = 'pendente';
    this.#renderizarTabela();
    status(this.mensagem, `${plural(this.selecionados.size, 'contrato com erro selecionado', 'contratos com erro selecionados')}. Corrija no SGP e clique em Iniciar.`);
  }

  #baixarCsv() {
    // texto do SGP começando com = + - @ viraria fórmula no Excel
    const campo = (v) => `"${String(v ?? '').replace(/^[=+\-@\t\r]/, "'$&").replace(/"/g, '""')}"`;
    const pendencias = (i) => (i.pendencias || []).map((p) => (p.detalhe ? `${p.titulo}: ${p.detalhe}` : p.titulo)).join(' | ');
    const linhas = [['Contrato', 'Cliente', 'Plano', 'Situação', 'Adicionar', 'Ativar', 'Causa', 'Cadastro', 'Mensagem']]
      .concat(this.itens.map((i) => [i.contrato, i.cliente, i.plano_internet, (SITUACOES[i.situacao] || ['', i.situacao])[1],
        i.faltando.join(', '), i.ativar.join(', '), (i.falhas || []).map((f) => f.titulo).join(', '), pendencias(i), i.msg]));
    const csv = '\ufeff' + linhas.map((l) => l.map(campo).join(';')).join('\r\n');
    const quando = new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-');
    baixar(`clientes-${slug(this.config.provedor || 'provedor')}-${quando}.csv`, csv, 'text/csv;charset=utf-8');
  }

  async #controlar(acao) {
    if (!this.tarefa) return;
    try {
      this.tarefa = await this.api.controlarTarefa(this.tarefa.id, acao);
      this.#renderizarAndamento();
    } catch (erro) {
      this.avisos.erro(erro.message);
    }
  }
}
