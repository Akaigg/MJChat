const Comum = (() => {
  const formatadorMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

  const icones = {
    chat: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    clipe: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
    enviar: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>',
    boleto: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8v8M9 8v8M11 8v8M14 8v8M16 8v8M18 8v8"/></svg>',
    visto: '<svg width="16" height="11" viewBox="0 0 16 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M1 6l3.5 3.5L11 2"/></svg>',
    vistoDuplo: '<svg width="18" height="11" viewBox="0 0 18 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M1 6l3.5 3.5L11 2"/><path d="M7.5 9.5L8 10l7-8"/></svg>',
    usuario: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
  };

  function escapar(texto) {
    return String(texto ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function linkificar(textoEscapado) {
    return textoEscapado.replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );
  }

  function formatarMoeda(valor) {
    return valor === null || valor === undefined ? "-" : formatadorMoeda.format(Number(valor));
  }

  function formatarData(iso) {
    if (!iso) return "-";
    const [ano, mes, dia] = iso.slice(0, 10).split("-");
    return `${dia}/${mes}/${ano}`;
  }

  function formatarHorario(iso) {
    const data = new Date(iso);
    const hora = data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    if (data.toDateString() === new Date().toDateString()) return hora;
    return `${data.toLocaleDateString("pt-BR")} ${hora}`;
  }

  function formatarVistoPorUltimo(iso) {
    if (!iso) return "offline";
    const data = new Date(iso);
    const hora = data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const ontem = new Date();
    ontem.setDate(ontem.getDate() - 1);
    if (data.toDateString() === new Date().toDateString()) return `visto por último hoje às ${hora}`;
    if (data.toDateString() === ontem.toDateString()) return `visto por último ontem às ${hora}`;
    return `visto por último em ${data.toLocaleDateString("pt-BR")} às ${hora}`;
  }

  function textoPresenca(online, vistoPorUltimo) {
    return online ? "online" : formatarVistoPorUltimo(vistoPorUltimo);
  }

  function formatarTelefone(telefone) {
    const digitos = String(telefone || "").replace(/\D/g, "");
    const local = digitos.length > 11 ? digitos.slice(-11) : digitos;
    const prefixo = digitos.length > 11 ? `+${digitos.slice(0, digitos.length - 11)} ` : "";
    if (local.length === 11) return `${prefixo}(${local.slice(0, 2)}) ${local.slice(2, 7)}-${local.slice(7)}`;
    if (local.length === 10) return `${prefixo}(${local.slice(0, 2)}) ${local.slice(2, 6)}-${local.slice(6)}`;
    return digitos;
  }

  function formatarCpf(cpf) {
    const digitos = String(cpf || "").replace(/\D/g, "");
    if (digitos.length !== 11) return digitos || "-";
    return `${digitos.slice(0, 3)}.${digitos.slice(3, 6)}.${digitos.slice(6, 9)}-${digitos.slice(9)}`;
  }

  function formatarTamanho(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function vencido(iso) {
    return iso && iso.slice(0, 10) < new Date().toISOString().slice(0, 10);
  }

  function dominio(url) {
    try {
      return new URL(url).hostname;
    } catch {
      return "";
    }
  }

  let temporizadorAviso;
  function avisar(texto) {
    let elemento = document.querySelector(".aviso-toast");
    if (!elemento) {
      elemento = document.createElement("div");
      elemento.className = "aviso-toast";
      document.body.appendChild(elemento);
    }
    elemento.textContent = texto;
    elemento.classList.remove("oculto");
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => elemento.classList.add("oculto"), 3500);
  }

  async function copiar(texto) {
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      const area = document.createElement("textarea");
      area.value = texto;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    avisar("Link copiado");
  }

  const sessao = {
    obterToken: () => sessionStorage.getItem("mjchat_token"),
    obterUsuario: () => JSON.parse(sessionStorage.getItem("mjchat_usuario") || "null"),
    salvar(token, usuario) {
      sessionStorage.setItem("mjchat_token", token);
      sessionStorage.setItem("mjchat_usuario", JSON.stringify(usuario));
    },
    sair() {
      sessionStorage.removeItem("mjchat_token");
      sessionStorage.removeItem("mjchat_usuario");
      location.href = "/login";
    },
    exigir(perfil) {
      const usuario = sessao.obterUsuario();
      if (!sessao.obterToken() || !usuario) {
        location.href = "/login";
        return null;
      }
      if (perfil && usuario.perfil !== perfil) {
        location.href = "/atendimento";
        return null;
      }
      return usuario;
    },
  };

  async function api(caminho, opcoes = {}) {
    const cabecalhos = { ...(opcoes.headers || {}) };
    const token = sessao.obterToken();
    if (token) cabecalhos.Authorization = `Bearer ${token}`;
    let corpo = opcoes.body;
    if (corpo && !(corpo instanceof FormData)) {
      cabecalhos["Content-Type"] = "application/json";
      corpo = JSON.stringify(corpo);
    }
    const resposta = await fetch(caminho, { ...opcoes, headers: cabecalhos, body: corpo });
    if (resposta.status === 401 && token) {
      sessao.sair();
      throw new Error("Sessão expirada");
    }
    if (!resposta.ok) {
      let detalhe = "Não foi possível concluir a operação";
      try {
        const dados = await resposta.json();
        if (typeof dados.detail === "string") detalhe = dados.detail;
        else if (Array.isArray(dados.detail)) detalhe = "Verifique os campos informados";
      } catch {}
      throw new Error(detalhe);
    }
    if (opcoes.binario) return resposta.blob();
    return resposta.status === 204 ? null : resposta.json();
  }

  function cartaoBoleto(boleto, credor) {
    const url = escapar(boleto.url);
    return `
      <div class="cartao-boleto">
        <div class="boleto-topo">
          ${icones.boleto}
          <div><strong>Boleto para pagamento</strong><span>${escapar(credor || "")}</span></div>
        </div>
        <dl class="boleto-dados">
          <div><dt>Valor</dt><dd>${formatarMoeda(boleto.valor)}</dd></div>
          <div><dt>Vencimento</dt><dd>${formatarData(boleto.vencimento)}</dd></div>
        </dl>
        <div class="boleto-acoes">
          <a class="botao" href="${url}" target="_blank" rel="noopener noreferrer">Abrir boleto</a>
          <button type="button" class="botao botao-secundario" data-copiar="${url}">Copiar link</button>
        </div>
        <div class="boleto-dominio">Emitido via ${escapar(dominio(boleto.url))}</div>
      </div>`;
  }

  function desenharConfirmacao(linha) {
    const elemento = linha.querySelector(".confirmacao");
    if (!elemento) return;
    const { enviada, entregue, lida } = linha.dataset;
    const detalhes = [`Enviada: ${formatarHorario(enviada)}`];
    if (entregue) detalhes.push(`Entregue: ${formatarHorario(entregue)}`);
    if (lida) detalhes.push(`Lida: ${formatarHorario(lida)}`);
    elemento.className = `confirmacao ${lida ? "lida" : entregue ? "entregue" : "enviada"}`;
    elemento.title = detalhes.join("\n");
    elemento.setAttribute("aria-label", lida ? "Lida" : entregue ? "Entregue" : "Enviada");
    elemento.innerHTML = lida || entregue ? icones.vistoDuplo : icones.visto;
  }

  function aplicarConfirmacoes(container, confirmacao) {
    confirmacao.ids.forEach((id) => {
      const linha = container.querySelector(`.linha-mensagem[data-id="${id}"]`);
      if (!linha) return;
      if (!linha.dataset.entregue) linha.dataset.entregue = confirmacao.momento;
      if (confirmacao.tipo === "lida" && !linha.dataset.lida) linha.dataset.lida = confirmacao.momento;
      desenharConfirmacao(linha);
    });
  }

  function criarMensagem(mensagem, opcoes) {
    const linha = document.createElement("div");
    linha.dataset.id = mensagem.id;
    if (mensagem.remetente === "sistema") {
      linha.className = "mensagem-sistema";
      linha.textContent = mensagem.conteudo;
      return linha;
    }
    const propria = mensagem.remetente === opcoes.perspectiva;
    linha.className = `linha-mensagem ${propria ? "propria" : "recebida"}`;
    let html = "";
    const mostrarAutor =
      mensagem.remetente === "operador" &&
      mensagem.nome_remetente &&
      (opcoes.perspectiva !== "operador" || opcoes.mostrarOperador);
    if (mostrarAutor) html += `<div class="autor">${escapar(mensagem.nome_remetente)}</div>`;
    const texto = mensagem.conteudo ? `<div class="texto">${linkificar(escapar(mensagem.conteudo))}</div>` : "";
    if (mensagem.boleto) html += texto + cartaoBoleto(mensagem.boleto, opcoes.credor);
    else if (mensagem.anexo) html += '<div class="espaco-anexo"></div>' + texto;
    else html += texto;
    const confirmacao = propria || opcoes.todasConfirmacoes ? '<span class="confirmacao"></span>' : "";
    html += `<div class="horario">${formatarHorario(mensagem.enviada_em)}${confirmacao}</div>`;
    const balao = document.createElement("div");
    balao.className = "balao";
    balao.innerHTML = html;
    linha.appendChild(balao);
    linha.dataset.enviada = mensagem.enviada_em;
    linha.dataset.entregue = mensagem.entregue_em || "";
    linha.dataset.lida = mensagem.lida_em || "";
    desenharConfirmacao(linha);
    if (mensagem.anexo) montarAnexo(balao.querySelector(".espaco-anexo"), mensagem.anexo, opcoes);
    return linha;
  }

  async function montarAnexo(espaco, anexo, opcoes) {
    const imagem = anexo.tipo_mime.startsWith("image/");
    const extensao = (anexo.nome.split(".").pop() || "").toUpperCase().slice(0, 4);
    if (imagem) {
      espaco.innerHTML = `<img class="anexo-imagem" alt="${escapar(anexo.nome)}">`;
    } else {
      espaco.innerHTML = `
        <a class="anexo-arquivo" target="_blank" rel="noopener" download="${escapar(anexo.nome)}">
          <span class="icone-arquivo">${escapar(extensao)}</span>
          <span><strong>${escapar(anexo.nome)}</strong><small>${formatarTamanho(anexo.tamanho)}</small></span>
        </a>`;
    }
    try {
      const url = await opcoes.urlAnexo(anexo);
      if (imagem) {
        const elemento = espaco.querySelector("img");
        elemento.addEventListener("load", () => opcoes.aoCarregarImagem && opcoes.aoCarregarImagem());
        elemento.src = url;
        elemento.addEventListener("click", () => ampliarImagem(url));
      } else {
        espaco.querySelector("a").href = url;
      }
    } catch {
      espaco.innerHTML = '<div class="texto-suave">Não foi possível carregar o anexo</div>';
    }
  }

  function ampliarImagem(url) {
    const fundo = document.createElement("div");
    fundo.className = "modal-fundo";
    fundo.innerHTML = `<img class="imagem-ampliada" src="${escapar(url)}" alt="">`;
    fundo.addEventListener("click", () => fundo.remove());
    document.body.appendChild(fundo);
  }

  function ativarCopia(container) {
    container.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-copiar]");
      if (botao) copiar(botao.dataset.copiar);
    });
  }

  function ajustarAltura(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
  }

  return {
    icones,
    escapar,
    formatarMoeda,
    formatarData,
    formatarHorario,
    formatarTelefone,
    formatarCpf,
    formatarVistoPorUltimo,
    textoPresenca,
    aplicarConfirmacoes,
    vencido,
    avisar,
    copiar,
    sessao,
    api,
    criarMensagem,
    ativarCopia,
    ajustarAltura,
  };
})();
