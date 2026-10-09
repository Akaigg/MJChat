(() => {
  const usuario = Comum.sessao.exigir();
  if (!usuario) return;

  const $ = (id) => document.getElementById(id);
  const elementos = {
    corpo: $("corpo"),
    lista: $("lista-conversas"),
    contadorFila: $("contador-fila"),
    contadorMeus: $("contador-meus"),
    vazio: $("vazio-chat"),
    ficha: $("ficha"),
    area: $("area-mensagens"),
    mensagens: $("lista-mensagens"),
    digitando: $("digitando"),
    compositor: $("compositor"),
    texto: $("texto"),
    arquivo: $("arquivo"),
    botaoAnexo: $("botao-anexo"),
    botaoEnviar: $("botao-enviar"),
    aviso: $("barra-aviso"),
    assumir: $("botao-assumir"),
    boleto: $("botao-boleto"),
    encerrar: $("botao-encerrar"),
    modalBoleto: $("modal-boleto"),
  };

  const rotulosStatus = {
    iniciada: "Iniciada",
    aguardando: "Aguardando",
    em_atendimento: "Em atendimento",
    encerrada: "Encerrada",
  };

  const estado = {
    aba: "fila",
    conversas: new Map(),
    naoLidas: new Set(),
    atual: null,
    idsExibidos: new Set(),
    anexos: new Map(),
    ultimoDigitando: 0,
  };
  let temporizadorDigitando;

  $("icone").innerHTML = Comum.icones.chat;
  elementos.botaoAnexo.innerHTML = Comum.icones.clipe;
  elementos.botaoEnviar.innerHTML = Comum.icones.enviar;
  $("identificacao").textContent = `${usuario.nome} · ${usuario.matricula}`;
  if (usuario.perfil === "admin") $("link-admin").classList.remove("oculto");
  $("botao-sair").addEventListener("click", Comum.sessao.sair);
  Comum.ativarCopia(elementos.mensagens);

  const socket = io({ auth: { token: Comum.sessao.obterToken() }, transports: ["websocket", "polling"] });

  function minha(conversa) {
    return conversa.status === "em_atendimento" && conversa.operador && conversa.operador.id === usuario.id;
  }

  function relevante(conversa) {
    return conversa.status === "aguardando" || minha(conversa);
  }

  function tocarAlerta() {
    try {
      const contexto = new (window.AudioContext || window.webkitAudioContext)();
      const oscilador = contexto.createOscillator();
      const volume = contexto.createGain();
      oscilador.frequency.value = 880;
      volume.gain.value = 0.08;
      oscilador.connect(volume).connect(contexto.destination);
      oscilador.start();
      oscilador.stop(contexto.currentTime + 0.18);
    } catch {}
  }

  function tempoDecorrido(iso) {
    const minutos = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
    if (minutos < 1) return "agora";
    if (minutos < 60) return `${minutos} min`;
    const horas = Math.floor(minutos / 60);
    return horas < 24 ? `${horas} h` : `${Math.floor(horas / 24)} d`;
  }

  function renderizarLista() {
    const todas = [...estado.conversas.values()];
    const fila = todas.filter((c) => c.status === "aguardando").sort((a, b) => a.iniciada_em.localeCompare(b.iniciada_em));
    const meus = todas.filter(minha).sort((a, b) => b.ultima_mensagem_em.localeCompare(a.ultima_mensagem_em));
    elementos.contadorFila.textContent = fila.length;
    elementos.contadorMeus.textContent = meus.length;
    const pendentes = [...estado.naoLidas].filter((id) => estado.conversas.has(id)).length;
    document.title = `${pendentes || fila.length ? `(${pendentes + fila.length}) ` : ""}MJChat - Atendimento`;

    const itens = estado.aba === "fila" ? fila : meus;
    if (!itens.length) {
      elementos.lista.innerHTML = `<li class="lista-vazia">${
        estado.aba === "fila" ? "Nenhum cliente aguardando no momento." : "Você não possui atendimentos em andamento."
      }</li>`;
      return;
    }
    elementos.lista.innerHTML = itens
      .map((conversa) => {
        const selecionada = estado.atual && estado.atual.id === conversa.id ? " selecionada" : "";
        const tempo = conversa.status === "aguardando"
          ? `aguardando há ${tempoDecorrido(conversa.iniciada_em)}`
          : Comum.formatarHorario(conversa.ultima_mensagem_em);
        return `
          <li class="item-conversa${selecionada}" data-id="${conversa.id}">
            <div class="linha"><strong>${Comum.escapar(conversa.cliente.nome)}</strong><small>${tempo}</small></div>
            <div class="credor">${Comum.escapar(conversa.cliente.credor)} · ${Comum.formatarMoeda(conversa.cliente.valor_divida)}</div>
            <div class="linha">
              <span class="previa">${Comum.escapar(conversa.previa || conversa.assunto || "")}</span>
              ${estado.naoLidas.has(conversa.id) ? '<span class="nao-lida"></span>' : ""}
            </div>
          </li>`;
      })
      .join("");
  }

  function renderizarFicha() {
    const conversa = estado.atual;
    if (!conversa) {
      elementos.vazio.classList.remove("oculto");
      [elementos.ficha, elementos.area, elementos.compositor, elementos.aviso].forEach((e) => e.classList.add("oculto"));
      elementos.corpo.classList.remove("com-conversa");
      return;
    }
    const cliente = conversa.cliente;
    elementos.vazio.classList.add("oculto");
    elementos.ficha.classList.remove("oculto");
    elementos.area.classList.remove("oculto");
    elementos.corpo.classList.add("com-conversa");
    $("ficha-nome").textContent = cliente.nome;
    const etiqueta = $("ficha-status");
    etiqueta.className = `etiqueta etiqueta-${conversa.status}`;
    etiqueta.textContent = rotulosStatus[conversa.status] || conversa.status;
    $("ficha-credor").textContent = cliente.credor;
    $("ficha-telefone").textContent = Comum.formatarTelefone(cliente.telefone);
    $("ficha-valor").textContent = Comum.formatarMoeda(cliente.valor_divida);
    $("ficha-vencimento").textContent =
      Comum.formatarData(cliente.data_vencimento) + (Comum.vencido(cliente.data_vencimento) ? " (vencido)" : "");
    $("ficha-assunto").textContent = conversa.assunto ? `Assunto: ${conversa.assunto}` : "Assunto ainda não informado";

    const podeAssumir = conversa.status === "aguardando" || conversa.status === "iniciada";
    const podeEscrever = minha(conversa);
    elementos.assumir.classList.toggle("oculto", !podeAssumir);
    elementos.boleto.classList.toggle("oculto", !podeEscrever);
    elementos.encerrar.classList.toggle("oculto", !podeEscrever);
    elementos.compositor.classList.toggle("oculto", !podeEscrever);

    let aviso = "";
    if (podeAssumir) aviso = "Assuma o atendimento para responder ao cliente.";
    else if (conversa.status === "encerrada") aviso = "Esta conversa foi encerrada.";
    else if (!podeEscrever) aviso = `Em atendimento com ${conversa.operador ? conversa.operador.nome : "outro operador"}.`;
    elementos.aviso.textContent = aviso;
    elementos.aviso.classList.toggle("oculto", !aviso);
  }

  async function urlAnexo(anexo) {
    if (!estado.anexos.has(anexo.id)) {
      const blob = await Comum.api(`/api/atendimento/anexos/${anexo.id}`, { binario: true });
      estado.anexos.set(anexo.id, URL.createObjectURL(blob));
    }
    return estado.anexos.get(anexo.id);
  }

  function rolarParaFim() {
    elementos.area.scrollTop = elementos.area.scrollHeight;
  }

  function adicionarMensagem(mensagem) {
    if (estado.idsExibidos.has(mensagem.id)) return;
    estado.idsExibidos.add(mensagem.id);
    const opcoes = {
      perspectiva: "operador",
      mostrarOperador: true,
      credor: estado.atual ? estado.atual.cliente.credor : "",
      urlAnexo,
      aoCarregarImagem: rolarParaFim,
    };
    elementos.mensagens.appendChild(Comum.criarMensagem(mensagem, opcoes));
    rolarParaFim();
  }

  function abrirConversa(id) {
    socket.timeout(10000).emit("abrir_conversa", { conversa_id: id }, (falhaRede, resposta) => {
      if (falhaRede) return Comum.avisar("Sem conexão com o servidor");
      if (resposta.erro) {
        Comum.avisar(resposta.erro);
        estado.conversas.delete(id);
        renderizarLista();
        return;
      }
      estado.atual = resposta.conversa;
      estado.naoLidas.delete(id);
      estado.idsExibidos.clear();
      elementos.mensagens.innerHTML = "";
      elementos.digitando.classList.add("oculto");
      resposta.mensagens.forEach(adicionarMensagem);
      renderizarFicha();
      renderizarLista();
      if (minha(estado.atual)) elementos.texto.focus();
    });
  }

  function fecharConversa() {
    estado.atual = null;
    socket.emit("fechar_conversa");
    renderizarFicha();
    renderizarLista();
  }

  async function carregarPainel() {
    try {
      const painel = await Comum.api("/api/atendimento/painel");
      estado.conversas.clear();
      [...painel.fila, ...painel.meus].forEach((c) => estado.conversas.set(c.id, c));
      renderizarLista();
    } catch (erro) {
      Comum.avisar(erro.message);
    }
  }

  function enviarMensagem(dados, aoConcluir) {
    elementos.botaoEnviar.disabled = true;
    socket.timeout(10000).emit("enviar_mensagem", { conversa_id: estado.atual.id, ...dados }, (falhaRede, resposta) => {
      elementos.botaoEnviar.disabled = false;
      if (falhaRede) return Comum.avisar("Sem conexão com o servidor");
      if (resposta.erro) return Comum.avisar(resposta.erro);
      aoConcluir && aoConcluir();
    });
  }

  function enviarTexto() {
    const conteudo = elementos.texto.value.trim();
    if (!conteudo || !estado.atual) return;
    enviarMensagem({ conteudo }, () => {
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
    try {
      await Comum.api(`/api/atendimento/conversas/${estado.atual.id}/anexos`, { method: "POST", body: formulario });
      elementos.texto.value = "";
      Comum.ajustarAltura(elementos.texto);
    } catch (erro) {
      Comum.avisar(erro.message);
    } finally {
      elementos.botaoAnexo.disabled = false;
      elementos.arquivo.value = "";
    }
  }

  socket.on("connect", () => {
    carregarPainel();
    if (estado.atual) abrirConversa(estado.atual.id);
  });

  socket.on("connect_error", (erro) => {
    if (erro.message === "nao_autorizado") Comum.sessao.sair();
  });

  socket.on("conversa_atualizada", (conversa) => {
    const anterior = estado.conversas.get(conversa.id);
    if (relevante(conversa)) {
      estado.conversas.set(conversa.id, conversa);
      const aberta = estado.atual && estado.atual.id === conversa.id;
      const novaNaFila = !anterior && conversa.status === "aguardando";
      const novaMensagem = anterior && anterior.ultima_mensagem_em !== conversa.ultima_mensagem_em;
      if (!aberta && (novaNaFila || (novaMensagem && minha(conversa)))) {
        estado.naoLidas.add(conversa.id);
        tocarAlerta();
      }
    } else {
      estado.conversas.delete(conversa.id);
      estado.naoLidas.delete(conversa.id);
    }
    if (estado.atual && estado.atual.id === conversa.id) {
      estado.atual = conversa;
      renderizarFicha();
    }
    renderizarLista();
  });

  socket.on("nova_mensagem", (mensagem) => {
    if (estado.atual && mensagem.conversa_id === estado.atual.id) {
      if (mensagem.remetente === "cliente") elementos.digitando.classList.add("oculto");
      adicionarMensagem(mensagem);
    }
  });

  socket.on("digitando", (dados) => {
    if (dados.remetente !== "cliente" || !estado.atual || dados.conversa_id !== estado.atual.id) return;
    elementos.digitando.classList.remove("oculto");
    clearTimeout(temporizadorDigitando);
    temporizadorDigitando = setTimeout(() => elementos.digitando.classList.add("oculto"), 3000);
  });

  document.querySelectorAll(".abas button").forEach((botao) => {
    botao.addEventListener("click", () => {
      document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b === botao));
      estado.aba = botao.dataset.aba;
      renderizarLista();
    });
  });

  elementos.lista.addEventListener("click", (evento) => {
    const item = evento.target.closest(".item-conversa");
    if (item) abrirConversa(Number(item.dataset.id));
  });

  $("botao-voltar").addEventListener("click", fecharConversa);

  elementos.assumir.addEventListener("click", async () => {
    elementos.assumir.disabled = true;
    try {
      const conversa = await Comum.api(`/api/atendimento/conversas/${estado.atual.id}/assumir`, { method: "POST" });
      estado.atual = conversa;
      estado.conversas.set(conversa.id, conversa);
      document.querySelector('.abas button[data-aba="meus"]').click();
      renderizarFicha();
      elementos.texto.focus();
    } catch (erro) {
      Comum.avisar(erro.message);
      carregarPainel();
    } finally {
      elementos.assumir.disabled = false;
    }
  });

  elementos.encerrar.addEventListener("click", async () => {
    if (!confirm("Deseja encerrar este atendimento? O cliente será avisado.")) return;
    try {
      estado.atual = await Comum.api(`/api/atendimento/conversas/${estado.atual.id}/encerrar`, { method: "POST" });
      renderizarFicha();
    } catch (erro) {
      Comum.avisar(erro.message);
    }
  });

  elementos.boleto.addEventListener("click", () => {
    const cliente = estado.atual.cliente;
    $("boleto-url").value = "";
    $("boleto-valor").value = cliente.valor_divida.toFixed(2);
    $("boleto-vencimento").value = cliente.data_vencimento;
    $("boleto-mensagem").value = "";
    elementos.modalBoleto.classList.remove("oculto");
    $("boleto-url").focus();
  });

  $("cancelar-boleto").addEventListener("click", () => elementos.modalBoleto.classList.add("oculto"));

  $("formulario-boleto").addEventListener("submit", (evento) => {
    evento.preventDefault();
    const boleto = {
      url: $("boleto-url").value.trim(),
      valor: $("boleto-valor").value,
      vencimento: $("boleto-vencimento").value,
    };
    enviarMensagem({ conteudo: $("boleto-mensagem").value.trim(), boleto }, () => {
      elementos.modalBoleto.classList.add("oculto");
    });
  });

  elementos.compositor.addEventListener("submit", (evento) => {
    evento.preventDefault();
    enviarTexto();
  });

  elementos.texto.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      enviarTexto();
    }
  });

  elementos.texto.addEventListener("input", () => {
    Comum.ajustarAltura(elementos.texto);
    const agora = Date.now();
    if (agora - estado.ultimoDigitando > 2500) {
      estado.ultimoDigitando = agora;
      socket.emit("digitando");
    }
  });

  elementos.botaoAnexo.addEventListener("click", () => elementos.arquivo.click());
  elementos.arquivo.addEventListener("change", () => {
    if (elementos.arquivo.files[0]) enviarArquivo(elementos.arquivo.files[0]);
  });

  setInterval(renderizarLista, 60000);
})();
