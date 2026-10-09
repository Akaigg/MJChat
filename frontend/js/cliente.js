(() => {
  const token = decodeURIComponent(location.pathname.split("/").filter(Boolean).pop() || "");
  const elementos = {
    avatar: document.getElementById("avatar"),
    empresa: document.getElementById("nome-empresa"),
    status: document.getElementById("status-atendimento"),
    erro: document.getElementById("tela-erro"),
    textoErro: document.getElementById("texto-erro"),
    area: document.getElementById("area-mensagens"),
    lista: document.getElementById("lista-mensagens"),
    digitando: document.getElementById("digitando"),
    compositor: document.getElementById("compositor"),
    texto: document.getElementById("texto"),
    arquivo: document.getElementById("arquivo"),
    botaoAnexo: document.getElementById("botao-anexo"),
    botaoEnviar: document.getElementById("botao-enviar"),
    encerrada: document.getElementById("barra-encerrada"),
    botaoNovo: document.getElementById("botao-novo"),
  };

  const estado = { cliente: null, conversa: null, idsExibidos: new Set(), socket: null, ultimoDigitando: 0 };
  let temporizadorDigitando;

  elementos.avatar.innerHTML = Comum.icones.chat;
  elementos.botaoAnexo.innerHTML = Comum.icones.clipe;
  elementos.botaoEnviar.innerHTML = Comum.icones.enviar;
  Comum.ativarCopia(elementos.lista);

  const opcoesMensagem = () => ({
    perspectiva: "cliente",
    credor: estado.cliente ? estado.cliente.credor : "",
    urlAnexo: (anexo) => Promise.resolve(`/api/cliente/${encodeURIComponent(token)}/anexos/${anexo.id}`),
    aoCarregarImagem: rolarParaFim,
  });

  function rolarParaFim() {
    elementos.area.scrollTop = elementos.area.scrollHeight;
  }

  function mostrarErro(texto) {
    elementos.erro.classList.remove("oculto");
    elementos.area.classList.add("oculto");
    elementos.compositor.classList.add("oculto");
    elementos.status.textContent = "Indisponível";
    if (texto) elementos.textoErro.textContent = texto;
  }

  function adicionarMensagem(mensagem) {
    if (estado.idsExibidos.has(mensagem.id)) return;
    estado.idsExibidos.add(mensagem.id);
    elementos.lista.appendChild(Comum.criarMensagem(mensagem, opcoesMensagem()));
    rolarParaFim();
  }

  function atualizarStatus(conversa) {
    estado.conversa = conversa;
    const textos = {
      iniciada: "Escreva o assunto do seu atendimento",
      aguardando: "Aguardando um operador",
      em_atendimento: conversa.operador_nome ? `Em atendimento com ${conversa.operador_nome}` : "Em atendimento",
      encerrada: "Atendimento encerrado",
    };
    elementos.status.textContent = textos[conversa.status] || "";
    const encerrada = conversa.status === "encerrada";
    elementos.compositor.classList.toggle("oculto", encerrada);
    elementos.encerrada.classList.toggle("oculto", !encerrada);
    elementos.texto.placeholder = conversa.status === "iniciada" ? "Escreva aqui o assunto" : "Digite sua mensagem";
  }

  async function carregar() {
    let dados;
    try {
      const resposta = await fetch(`/api/cliente/${encodeURIComponent(token)}`);
      if (!resposta.ok) {
        mostrarErro();
        return false;
      }
      dados = await resposta.json();
    } catch {
      mostrarErro("Não foi possível conectar. Verifique sua internet e tente novamente.");
      return false;
    }
    estado.cliente = dados.cliente;
    document.title = `Atendimento - ${dados.empresa}`;
    elementos.empresa.textContent = dados.empresa;
    elementos.lista.innerHTML = "";
    estado.idsExibidos.clear();
    dados.mensagens.forEach(adicionarMensagem);
    atualizarStatus(dados.conversa);
    return true;
  }

  function conectar() {
    estado.socket = io({ auth: { cliente: token }, transports: ["websocket", "polling"] });
    let primeiraConexao = true;
    estado.socket.on("connect", () => {
      if (!primeiraConexao) carregar();
      primeiraConexao = false;
    });
    estado.socket.on("connect_error", (erro) => {
      if (erro.message === "link_invalido") mostrarErro();
    });
    estado.socket.on("nova_mensagem", (mensagem) => {
      elementos.digitando.classList.add("oculto");
      adicionarMensagem(mensagem);
    });
    estado.socket.on("status_conversa", atualizarStatus);
    estado.socket.on("digitando", (dados) => {
      if (dados.remetente !== "operador") return;
      elementos.digitando.classList.remove("oculto");
      clearTimeout(temporizadorDigitando);
      temporizadorDigitando = setTimeout(() => elementos.digitando.classList.add("oculto"), 3000);
    });
  }

  function enviarTexto() {
    const conteudo = elementos.texto.value.trim();
    if (!conteudo) return;
    elementos.botaoEnviar.disabled = true;
    estado.socket.timeout(10000).emit("enviar_mensagem", { conteudo }, (falhaRede, resposta) => {
      elementos.botaoEnviar.disabled = false;
      if (falhaRede) {
        Comum.avisar("Sem conexão. Tente novamente.");
        return;
      }
      if (resposta && resposta.erro) {
        Comum.avisar(resposta.erro);
        return;
      }
      elementos.texto.value = "";
      Comum.ajustarAltura(elementos.texto);
      elementos.texto.focus();
    });
  }

  async function enviarArquivo(arquivo) {
    const formulario = new FormData();
    formulario.append("arquivo", arquivo);
    formulario.append("legenda", elementos.texto.value.trim());
    elementos.botaoAnexo.disabled = true;
    Comum.avisar("Enviando arquivo...");
    try {
      const resposta = await fetch(`/api/cliente/${encodeURIComponent(token)}/anexos`, { method: "POST", body: formulario });
      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}));
        throw new Error(typeof dados.detail === "string" ? dados.detail : "Falha ao enviar o arquivo");
      }
      elementos.texto.value = "";
      Comum.ajustarAltura(elementos.texto);
      Comum.avisar("Arquivo enviado");
    } catch (erro) {
      Comum.avisar(erro.message);
    } finally {
      elementos.botaoAnexo.disabled = false;
      elementos.arquivo.value = "";
    }
  }

  elementos.compositor.addEventListener("submit", (evento) => {
    evento.preventDefault();
    enviarTexto();
  });

  elementos.texto.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey && window.matchMedia("(pointer: fine)").matches) {
      evento.preventDefault();
      enviarTexto();
    }
  });

  elementos.texto.addEventListener("input", () => {
    Comum.ajustarAltura(elementos.texto);
    const agora = Date.now();
    if (estado.socket && agora - estado.ultimoDigitando > 2500) {
      estado.ultimoDigitando = agora;
      estado.socket.emit("digitando");
    }
  });

  elementos.botaoAnexo.addEventListener("click", () => elementos.arquivo.click());
  elementos.arquivo.addEventListener("change", () => {
    if (elementos.arquivo.files[0]) enviarArquivo(elementos.arquivo.files[0]);
  });

  elementos.botaoNovo.addEventListener("click", async () => {
    if (estado.socket) estado.socket.disconnect();
    if (await carregar()) conectar();
  });

  carregar().then((sucesso) => {
    if (sucesso) conectar();
  });
})();
