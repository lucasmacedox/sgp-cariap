import { problemasDoMapeamento, reagrupar, servicosPorPlano } from '../dominio.js';
import { Eventos } from '../estado.js';
import { $, alternar, esc, icone, info, moeda, plural } from '../util.js';
import { Tela } from './base.js';

const ehCariap = (servico) => /cariap/i.test(servico.gateway || '');

// o SGP identifica o plano pelo nome; nomes repetidos não podem ser vinculados
function nomesRepetidos(planos) {
  const contagem = new Map();
  for (const { nome } of planos) contagem.set(nome.toLowerCase(), (contagem.get(nome.toLowerCase()) ?? 0) + 1);
  return new Set([...contagem].filter(([, n]) => n > 1).map(([nome]) => nome));
}
const AVISO_REPETIDO = `<div class="nota-aviso">Nome repetido ${info('O SGP identifica o plano pelo nome. Renomeie no SGP para poder vincular.')}</div>`;

export class TelaMapeamento extends Tela {
  constructor(contexto) {
    super(contexto);
    this.selecionados = new Set();
    this.corpo = $('#tb-mapeamento tbody');
    this.corpoServicos = $('#tb-servicos tbody');
    this.listaGrupos = $('#lista-grupos');

    for (const filtro of ['#mp-filtro', '#mp-com-clientes', '#mp-sem-grupo']) {
      $(filtro).addEventListener('input', () => this.#renderizarPlanos());
    }
    for (const filtro of ['#mp-filtro-servicos', '#mp-so-cariap']) {
      $(filtro).addEventListener('input', () => this.#renderizarServicos());
    }
    $('#mp-todos').addEventListener('change', (e) => this.#selecionarVisiveis(e.target.checked));
    // o cabeçalho da tabela gruda logo abaixo da barra de filtros, que muda de altura ao quebrar linha
    const topo = $('.mp-topo');
    new ResizeObserver(() => topo.parentElement.style.setProperty('--mp-topo', `${topo.offsetHeight}px`)).observe(topo);
    this.corpo.addEventListener('click', (e) => this.#alternarPlano(e));
    this.corpoServicos.addEventListener('click', (e) => this.#alternarServico(e));
    $('#mp-mover').addEventListener('change', (e) => this.#copiarServicosDoGrupo(e.target));
    $('#mp-tirar').addEventListener('click', () => this.#aplicar(() => []));
    $('#mp-limpar').addEventListener('click', () => { this.selecionados.clear(); this.#renderizarTudo(); });
    this.listaGrupos.addEventListener('input', (e) => this.#editarNome(e.target));
    this.listaGrupos.addEventListener('change', (e) => this.#adicionarServicoAoGrupo(e.target));
    this.listaGrupos.addEventListener('click', (e) => this.#acaoNoGrupo(e));

    this.quando([Eventos.PLANOS], () => this.#ajustarFiltroCariap());
    this.quando([Eventos.PLANOS, Eventos.RECARREGADA], () => this.renderizar());
    this.renderizar();
  }

  get planosSgp() {
    return this.estado.planos?.planos_internet ?? [];
  }

  get servicosSgp() {
    return this.estado.planos?.planos_servico ?? [];
  }

  renderizar() {
    const carregado = Boolean(this.estado.planos);
    $('#mp-vazio').hidden = carregado;
    $('#mp-conteudo').hidden = !carregado;
    if (!carregado) return;
    $('#dl-servicos').innerHTML = this.servicosSgp
      .map((s) => `<option value="${esc(s.nome)}">${esc(s.gateway || 'sem gateway')} · ${s.ativos} ativos</option>`).join('');
    this.#renderizarTudo();
  }

  #ajustarFiltroCariap() {
    $('#mp-so-cariap').checked = this.servicosSgp.some(ehCariap);
  }

  #renderizarTudo() {
    this.#renderizarPlanos();
    this.#renderizarServicos();
    this.#renderizarGrupos();
  }

  #visiveis() {
    const termo = $('#mp-filtro').value.trim().toLowerCase();
    const comClientes = $('#mp-com-clientes').checked;
    const semServicos = $('#mp-sem-grupo').checked;
    const atuais = servicosPorPlano(this.config);
    return this.planosSgp
      .filter((p) => (!comClientes || p.ativos > 0) && (!termo || p.rotulo.toLowerCase().includes(termo))
        && (!semServicos || !atuais.get(p.rotulo)?.length))
      .sort((a, b) => b.ativos - a.ativos || a.rotulo.localeCompare(b.rotulo, 'pt-BR'));
  }

  #renderizarPlanos() {
    const visiveis = this.#visiveis();
    const atuais = servicosPorPlano(this.config);
    const repetidos = nomesRepetidos(this.planosSgp);
    this.corpo.innerHTML = visiveis.map((p) => {
      const servicos = atuais.get(p.rotulo) ?? [];
      const marcado = this.selecionados.has(p.rotulo);
      const repetido = repetidos.has(p.nome.toLowerCase());
      return `<tr class="${marcado ? 'marcado' : ''}${repetido ? ' desabilitado' : ''}" data-rotulo="${esc(p.rotulo)}">
        <td class="caixa"><input type="checkbox" ${marcado ? 'checked' : ''} ${repetido ? 'disabled' : ''} aria-label="Selecionar ${esc(p.rotulo)}"></td>
        <td>${esc(p.nome)} <span class="sutil">· ${esc(p.grupo)}</span>${repetido ? AVISO_REPETIDO : ''}</td>
        <td class="num" data-th="Preço">${p.preco != null ? moeda(p.preco) : '<span class="sutil">-</span>'}</td>
        <td class="num" data-th="Ativos">${p.ativos}</td>
        <td class="servicos" data-th="Serviços">${servicos.length ? esc(servicos.join(', ')) : '<span class="sem-grupo">—</span>'}</td></tr>`;
    }).join('') || '<tr><td colspan="5" class="vazio">Nenhum plano encontrado.</td></tr>';
    $('#mp-todos').checked = visiveis.length > 0 && visiveis.every((p) => this.selecionados.has(p.rotulo));
    this.#renderizarSelecao();
  }

  #renderizarSelecao() {
    const total = this.selecionados.size;
    $('#mp-selecao').hidden = total === 0;
    $('#mp-selecao-texto').textContent = plural(total, 'selecionado', 'selecionados');
    $('#mp-mover').innerHTML = '<option value="">Copiar serviços de…</option>'
      + this.config.grupos.map((g, i) => `<option value="${i}">${esc(g.nome)}</option>`).join('');
    $('#mp-alvo').innerHTML = total
      ? `Aplicando a <b>${plural(total, 'plano', 'planos')}</b>`
      : 'Selecione planos de internet primeiro';
  }

  #alternarPlano(evento) {
    const linha = evento.target.closest('tr[data-rotulo]');
    if (!linha) return;
    const caixa = $('input', linha);
    if (caixa.disabled) return;
    if (evento.target !== caixa) caixa.checked = !caixa.checked;
    alternar(this.selecionados, linha.dataset.rotulo, caixa.checked);
    linha.classList.toggle('marcado', caixa.checked);
    this.#renderizarSelecao();
    this.#renderizarServicos();
  }

  #selecionarVisiveis(marcar) {
    const repetidos = nomesRepetidos(this.planosSgp);
    for (const plano of this.#visiveis().filter((p) => !repetidos.has(p.nome.toLowerCase()))) {
      alternar(this.selecionados, plano.rotulo, marcar);
    }
    this.#renderizarPlanos();
    this.#renderizarServicos();
  }

  #renderizarServicos() {
    const termo = $('#mp-filtro-servicos').value.trim().toLowerCase();
    const soCariap = $('#mp-so-cariap').checked;
    const atuais = servicosPorPlano(this.config);
    const selecionados = [...this.selecionados];
    const repetidos = nomesRepetidos(this.servicosSgp);
    const servicos = this.servicosSgp
      .filter((s) => (!soCariap || ehCariap(s)) && (!termo || s.nome.toLowerCase().includes(termo)))
      .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
    this.corpoServicos.innerHTML = servicos.map((s) => {
      const com = selecionados.filter((p) => (atuais.get(p) ?? []).includes(s.nome)).length;
      const todos = selecionados.length > 0 && com === selecionados.length;
      const alguns = com > 0 && !todos;
      const repetido = repetidos.has(s.nome.toLowerCase());
      const habilitado = selecionados.length > 0 && !repetido;
      return `<tr class="${habilitado ? '' : 'desabilitado'}${todos ? ' vinculado' : ''}" data-servico="${esc(s.nome)}">
        <td class="caixa"><input type="checkbox" ${todos ? 'checked' : ''} ${alguns && !repetido ? 'data-parcial' : ''}
          ${habilitado ? '' : 'disabled'} aria-label="Vincular ${esc(s.nome)}"></td>
        <td>${esc(s.nome)}${repetido ? AVISO_REPETIDO : ''}</td><td class="gateway" data-th="Gateway">${esc(s.gateway && s.gateway !== '-' ? s.gateway : '—')}</td><td class="num" data-th="Ativos">${s.ativos}</td></tr>`;
    }).join('') || `<tr><td colspan="4" class="vazio">${soCariap ? 'Nenhum serviço Cariap. Desmarque “Só Cariap” para ver todos.' : 'Nenhum serviço encontrado.'}</td></tr>`;
    // estado intermediário: só parte dos planos selecionados tem o serviço
    for (const caixa of this.corpoServicos.querySelectorAll('input[data-parcial]')) caixa.indeterminate = true;
  }

  #alternarServico(evento) {
    const linha = evento.target.closest('tr[data-servico]');
    const caixa = linha && $('input', linha);
    if (!caixa || caixa.disabled) return;
    if (evento.target !== caixa) caixa.checked = !caixa.checked;
    const servico = linha.dataset.servico;
    const vincular = caixa.checked;
    this.#aplicar((servicos) => (vincular
      ? [...new Set([...servicos, servico])]
      : servicos.filter((s) => s !== servico)));
  }

  // aplica a transformação aos serviços de cada plano e refaz os grupos
  #aplicar(transformar, planos = this.selecionados) {
    const mapa = servicosPorPlano(this.config);
    for (const plano of planos) mapa.set(plano, transformar(mapa.get(plano) ?? []));
    reagrupar(this.config, mapa);
    this.#salvar();
  }

  #copiarServicosDoGrupo(campo) {
    const grupo = this.config.grupos[Number(campo.value)];
    campo.value = '';
    if (grupo) this.#aplicar(() => [...grupo.servicos]);
  }

  #renderizarGrupos() {
    const porRotulo = new Map(this.planosSgp.map((p) => [p.rotulo, p]));
    const servicosSgp = new Set(this.servicosSgp.map((s) => s.nome));
    const ausente = (existe) => (existe ? '' : ' ausente" data-dica="Não encontrado no SGP');
    this.listaGrupos.innerHTML = this.config.grupos.map((grupo, i) => {
      const ativos = grupo.planos.reduce((total, p) => total + (porRotulo.get(p)?.ativos ?? 0), 0);
      const servicos = grupo.servicos.map((s, j) => `<span class="etiqueta servico${ausente(servicosSgp.has(s))}">${esc(s)}
        <button type="button" data-acao="tirar-servico" data-grupo="${i}" data-j="${j}" aria-label="Remover serviço" data-dica="Remover do grupo">${icone('remover')}</button></span>`).join('');
      const planos = grupo.planos.map((p, j) => `<span class="etiqueta${ausente(porRotulo.has(p))}">${esc(p.split(' - ').slice(1).join(' - ') || p)}
        <button type="button" data-acao="tirar-plano" data-grupo="${i}" data-j="${j}" aria-label="Remover plano" data-dica="Remover do grupo (fica sem serviços)">${icone('remover')}</button></span>`).join('');
      return `<article class="cartao grupo" data-gi="${i}">
        <div class="grupo-cab">
          <input data-grupo-nome="${i}" value="${esc(grupo.nome)}" aria-label="Nome do grupo">
          <button class="btn sutil pequeno" type="button" data-acao="selecionar" data-grupo="${i}" data-dica="Selecionar estes planos na tabela">Selecionar</button>
          <button class="btn-icone perigo" type="button" data-acao="excluir" data-grupo="${i}" aria-label="Desfazer grupo" data-dica="Desfazer grupo">${icone('lixeira')}</button>
        </div>
        <div>
          <p class="subtitulo">Serviços</p>
          <div class="etiquetas">${servicos}</div>
        </div>
        <input data-servico-add="${i}" list="dl-servicos" placeholder="Adicionar serviço" aria-label="Adicionar serviço ao grupo">
        <div>
          <p class="subtitulo">Planos · ${grupo.planos.length}</p>
          <div class="etiquetas">${planos}</div>
        </div>
        <div class="grupo-rodape"><span>${plural(ativos, 'cliente ativo', 'clientes ativos')}</span></div>
      </article>`;
    }).join('');
    const problemas = problemasDoMapeamento(this.config);
    $('#mp-problemas').hidden = problemas.length === 0;
    $('#mp-problemas').textContent = problemas.length ? `Pendências: ${problemas.join('; ')}.` : '';
  }

  #editarNome(campo) {
    const indice = campo.dataset.grupoNome;
    if (indice === undefined) return;
    this.config.grupos[indice].nome = campo.value;
    this.estado.alterar();
    this.#renderizarSelecao();
  }

  #adicionarServicoAoGrupo(campo) {
    const indice = campo.dataset.servicoAdd;
    if (indice === undefined) return;
    const servico = campo.value.trim();
    if (!servico || !this.servicosSgp.some((s) => s.nome === servico)) return;
    campo.value = ''; // sem valor pendente, o redesenho não dispara outro "change"
    this.#aplicar((servicos) => [...new Set([...servicos, servico])], this.config.grupos[indice].planos);
  }

  #acaoNoGrupo(evento) {
    const botao = evento.target.closest('button[data-acao]');
    if (!botao) return;
    const grupo = this.config.grupos[botao.dataset.grupo];
    const j = Number(botao.dataset.j);
    switch (botao.dataset.acao) {
      case 'tirar-servico': {
        const servico = grupo.servicos[j];
        this.#aplicar((servicos) => servicos.filter((s) => s !== servico), grupo.planos);
        break;
      }
      case 'tirar-plano':
        this.#aplicar(() => [], [grupo.planos[j]]);
        break;
      case 'selecionar':
        this.selecionados = new Set(grupo.planos);
        this.#renderizarTudo();
        break;
      case 'excluir':
        if (!confirm(`Desfazer “${grupo.nome}”? ${plural(grupo.planos.length, 'plano fica', 'planos ficam')} sem serviços.`)) return;
        this.#aplicar(() => [], grupo.planos);
        break;
    }
  }

  #salvar() {
    this.estado.alterar();
    this.#renderizarTudo();
  }
}
