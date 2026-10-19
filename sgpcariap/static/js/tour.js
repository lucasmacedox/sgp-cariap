import { armazenamento } from './util.js';

const CHAVE_VISTO = 'sgpcariap.tour.v1';

const ROTEIRO = {
  conexao: [
    ['#passos', 'Três etapas', 'Conectar, escolher os serviços de cada plano e aplicar nos clientes. O assistente só lê os planos do SGP.', 'right'],
    ['#provedor-box', 'Provedores', 'Cada provedor tem seu próprio SGP, serviços e filtros.', 'right'],
    ['#cx-url', 'Endereço do SGP', 'O mesmo do navegador. Para testar: <code>https://demo.sgp.net.br</code>, usuário e senha <code>demo</code>.'],
    ['#btn-conectar', 'Conectar', 'A senha fica só na memória. Ao entrar, os planos são lidos.'],
  ],
  mapeamento: [
    ['#tb-mapeamento', 'Planos de internet', 'Clique para selecionar um ou vários planos.'],
    ['#tb-servicos', 'Serviços de TV', 'Marque os serviços que cada plano selecionado deve receber.', 'left'],
    ['#lista-grupos', 'Grupos', 'Planos com os mesmos serviços se agrupam sozinhos.', 'left'],
  ],
  lote: [
    ['#lt-filtros', 'Quem recebe', 'Contratos ativos dos planos mapeados. Restrinja por plano ou POP se quiser.'],
    ['#btn-lote-buscar', 'Buscar', 'Mostra o que falta em cada contrato e confere e-mail, celular e CPF. Desmarque quem não deve receber.'],
    ['#btn-lote-iniciar', 'Iniciar', 'Um contrato por vez, com pausa e parada. Rodar de novo só faz o que falta.'],
    ['#btn-ajuda', 'Ajuda', 'Reabra o tour quando quiser.', 'right'],
  ],
};

export class TourGuiado {
  constructor(navegacao) {
    this.navegacao = navegacao;
    this.criarDriver = window.driver?.js?.driver;
    if (!this.disponivel) {
      for (const botao of document.querySelectorAll('[data-explicar], [data-tour="secao"], [data-tour="completo"]')) botao.hidden = true;
    }
  }

  get disponivel() {
    return typeof this.criarDriver === 'function';
  }

  explicar(etapa) {
    this.#rodar([ROTEIRO[etapa] ? etapa : 'conexao']);
  }

  completo() {
    this.#rodar(Object.keys(ROTEIRO));
  }

  abrirNaPrimeiraVisita() {
    if (armazenamento.ler(CHAVE_VISTO)) return;
    setTimeout(() => this.completo(), 400);
  }

  #rodar(etapas) {
    if (!this.disponivel) return;
    const passos = etapas.flatMap((etapa) => ROTEIRO[etapa].map(([elemento, titulo, texto, lado]) => ({
      etapa,
      element: elemento,
      popover: { title: titulo, description: texto, side: lado || 'bottom', align: 'start' },
    })));
    const irPara = (indice) => {
      const passo = passos[indice];
      if (passo && passo.etapa !== this.navegacao.atual) this.navegacao.mostrar(passo.etapa);
    };

    irPara(0);
    const tour = this.criarDriver({
      steps: passos,
      showProgress: true,
      progressText: '{{current}} de {{total}}',
      nextBtnText: 'Próximo',
      prevBtnText: 'Voltar',
      doneBtnText: 'Concluir',
      smoothScroll: true,
      // A etapa precisa estar visível antes de o driver procurar o elemento.
      onNextClick: () => {
        const proximo = tour.getActiveIndex() + 1;
        if (proximo >= passos.length) return tour.destroy();
        irPara(proximo);
        return tour.moveNext();
      },
      onPrevClick: () => {
        irPara(tour.getActiveIndex() - 1);
        tour.movePrevious();
      },
      onDestroyed: () => armazenamento.gravar(CHAVE_VISTO, true),
    });
    tour.drive();
  }
}
