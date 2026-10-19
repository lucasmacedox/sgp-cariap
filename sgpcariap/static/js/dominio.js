export const VERSAO_CONFIG = 2;

const PADROES = Object.freeze({ grupo_tv: 'TV', modo_aquisicao: 'Comodato' });
const LOTE = Object.freeze({
  planos: [], pops: [], status_contrato: ['Ativo'], ativar: true, validar_cadastro: true, pausa_segundos: 2, limite: '',
});

export const novaConfiguracao = (provedor = 'Novo provedor') => ({
  versao: VERSAO_CONFIG,
  provedor,
  sgp: { url: '', usuario: '', ignorar_ssl: false },
  padroes: { ...PADROES },
  grupos: [],
  lote: structuredClone(LOTE),
});

// arquivos da versão anterior só têm conexão e nome
export function normalizarConfiguracao(dados, provedor) {
  const base = novaConfiguracao(provedor || dados?.provedor);
  return {
    ...base,
    provedor: provedor || dados?.provedor || base.provedor,
    sgp: { ...base.sgp, ...(dados?.sgp || {}) },
    padroes: { ...PADROES, ...(dados?.padroes || {}) },
    grupos: Array.isArray(dados?.grupos) ? dados.grupos.map((g) => ({ nome: '', planos: [], servicos: [], ...g })) : [],
    lote: { ...structuredClone(LOTE), ...(dados?.lote || {}) },
  };
}

// mesmas regras do servidor
export function problemasDoMapeamento(config) {
  const problemas = [];
  const dono = new Map();
  for (const grupo of config.grupos) {
    const nome = grupo.nome || 'grupo sem nome';
    if (!grupo.planos.length) problemas.push(`${nome}: nenhum plano de internet`);
    if (!grupo.servicos.length) problemas.push(`${nome}: nenhum serviço definido`);
    for (const plano of grupo.planos) {
      const chave = plano.toLowerCase();
      if (dono.has(chave) && dono.get(chave) !== nome) problemas.push(`o plano "${plano}" está em dois grupos`);
      if (!dono.has(chave)) dono.set(chave, nome);
    }
  }
  return problemas;
}

const chaveServicos = (servicos) => [...servicos].map((s) => s.toLowerCase()).sort().join('|');

export function servicosPorPlano(config) {
  const mapa = new Map();
  for (const grupo of config.grupos) for (const plano of grupo.planos) mapa.set(plano, [...grupo.servicos]);
  return mapa;
}

// planos com os mesmos serviços ficam juntos; o grupo que mantém o conjunto conserva o nome
export function reagrupar(config, mapa) {
  const nomes = new Map(config.grupos.map((g) => [chaveServicos(g.servicos), g.nome]));
  const grupos = new Map();
  for (const [plano, servicos] of mapa) {
    if (!servicos.length) continue;
    const chave = chaveServicos(servicos);
    if (!grupos.has(chave)) {
      grupos.set(chave, { nome: nomes.get(chave) || servicos.join(' + '), planos: [], servicos: [...servicos] });
    }
    grupos.get(chave).planos.push(plano);
  }
  config.grupos = [...grupos.values()];
}
