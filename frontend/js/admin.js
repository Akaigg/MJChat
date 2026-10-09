(() => {
  const usuario = Comum.sessao.exigir("admin");
  if (!usuario) return;

  const $ = (id) => document.getElementById(id);
  const rotulosStatus = {
    iniciada: "Iniciada",
    aguardando: "Aguardando",
    em_atendimento: "Em atendimento",
    encerrada: "Encerrada",
  };
  const estado = { operadores: [], clientes: [], clienteEditado: null, pagina: 1, paginas: 1, operadorSenha: null };

  $("icone").innerHTML = Comum.icones.chat;
  $("identificacao").textContent = `${usuario.nome} · ${usuario.matricula}`;
  $("botao-sair").addEventListener("click", Comum.sessao.sair);
  Comum.ativarCopia(document.body);

  document.querySelectorAll(".abas button").forEach((botao) => {
    botao.addEventListener("click", () => {
      document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b === botao));
      document.querySelectorAll(".secao").forEach((secao) => secao.classList.add("oculto"));
      $(`aba-${botao.dataset.aba}`).classList.remove("oculto");
      if (botao.dataset.aba === "clientes") carregarClientes();
      if (botao.dataset.aba === "conversas") carregarConversas();
    });
  });

  async function senhaAleatoria(campo) {
    try {
      campo.value = (await Comum.api("/api/admin/senha-aleatoria")).senha;
    } catch (erro) {
      Comum.avisar(erro.message);
    }
  }

  async function carregarOperadores() {
    try {
      estado.operadores = await Comum.api("/api/admin/usuarios");
    } catch (erro) {
      return Comum.avisar(erro.message);
    }
    $("tabela-operadores").innerHTML = estado.operadores
      .map(
        (operador) => `
        <tr>
          <td><strong>${Comum.escapar(operador.matricula)}</strong></td>
          <td>${Comum.escapar(operador.nome)}</td>
          <td>${operador.perfil === "admin" ? "Administrador" : "Operador"}</td>
          <td><span class="etiqueta ${operador.ativo ? "etiqueta-em_atendimento" : "etiqueta-encerrada"}">${operador.ativo ? "Ativo" : "Inativo"}</span></td>
          <td>${operador.ultimo_acesso ? Comum.formatarHorario(operador.ultimo_acesso) : "-"}</td>
          <td class="acoes-tabela">
            <button type="button" class="botao botao-secundario" data-senha="${operador.id}">Redefinir senha</button>
            <button type="button" class="botao ${operador.ativo ? "botao-perigo" : "botao-secundario"}" data-ativo="${operador.id}">
              ${operador.ativo ? "Desativar" : "Ativar"}
            </button>
          </td>
        </tr>`
      )
      .join("");
  }

  $("operador-matricula").addEventListener("input", (evento) => {
    evento.target.value = evento.target.value.replace(/\D/g, "").slice(0, 4);
  });
  $("gerar-senha").addEventListener("click", () => senhaAleatoria($("operador-senha")));

  $("formulario-operador").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await Comum.api("/api/admin/usuarios", {
        method: "POST",
        body: {
          matricula: $("operador-matricula").value,
          nome: $("operador-nome").value,
          perfil: $("operador-perfil").value,
          senha: $("operador-senha").value,
        },
      });
      evento.target.reset();
      Comum.avisar("Operador cadastrado");
      carregarOperadores();
    } catch (erro) {
      Comum.avisar(erro.message);
    }
  });

  $("tabela-operadores").addEventListener("click", async (evento) => {
    const botaoSenha = evento.target.closest("[data-senha]");
    const botaoAtivo = evento.target.closest("[data-ativo]");
    if (botaoSenha) {
      const operador = estado.operadores.find((o) => o.id === Number(botaoSenha.dataset.senha));
      estado.operadorSenha = operador.id;
      $("senha-operador").textContent = `${operador.matricula} · ${operador.nome}`;
      $("nova-senha").value = "";
      $("modal-senha").classList.remove("oculto");
      $("nova-senha").focus();
    }
    if (botaoAtivo) {
      const operador = estado.operadores.find((o) => o.id === Number(botaoAtivo.dataset.ativo));
      if (operador.ativo && !confirm(`Desativar ${operador.nome}? Ele não conseguirá mais acessar o sistema.`)) return;
      try {
        await Comum.api(`/api/admin/usuarios/${operador.id}`, { method: "PATCH", body: { ativo: !operador.ativo } });
        carregarOperadores();
      } catch (erro) {
        Comum.avisar(erro.message);
      }
    }
  });

  $("gerar-nova-senha").addEventListener("click", () => senhaAleatoria($("nova-senha")));
  $("cancelar-senha").addEventListener("click", () => $("modal-senha").classList.add("oculto"));
  $("formulario-senha").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await Comum.api(`/api/admin/usuarios/${estado.operadorSenha}`, {
        method: "PATCH",
        body: { senha: $("nova-senha").value },
      });
      $("modal-senha").classList.add("oculto");
      Comum.avisar("Senha redefinida");
    } catch (erro) {
      Comum.avisar(erro.message);
    }
  });

  async function carregarClientes() {
    try {
      const busca = encodeURIComponent($("busca-cliente").value.trim());
      estado.clientes = await Comum.api(`/api/admin/clientes?busca=${busca}`);
    } catch (erro) {
      return Comum.avisar(erro.message);
    }
    if (!estado.clientes.length) {
      $("tabela-clientes").innerHTML = '<tr><td colspan="7" class="texto-suave">Nenhum cliente encontrado.</td></tr>';
      return;
    }
    $("tabela-clientes").innerHTML = estado.clientes
      .map(
        (cliente) => `
        <tr>
          <td>${Comum.escapar(cliente.nome)}</td>
          <td>${Comum.formatarCpf(cliente.cpf)}</td>
          <td>${Comum.formatarTelefone(cliente.telefone)}</td>
          <td>${Comum.escapar(cliente.credor)}</td>
          <td>${Comum.formatarMoeda(cliente.valor_divida)}</td>
          <td>${Comum.formatarData(cliente.data_vencimento)}</td>
          <td class="acoes-tabela">
            <button type="button" class="botao botao-secundario" data-copiar="${Comum.escapar(cliente.link)}">Copiar link</button>
            <button type="button" class="botao botao-secundario" data-editar="${cliente.id}">Editar</button>
          </td>
        </tr>`
      )
      .join("");
  }

  function limparFormularioCliente() {
    estado.clienteEditado = null;
    $("formulario-cliente").reset();
    $("titulo-cliente").textContent = "Cadastrar cliente e gerar link de atendimento";
    $("cancelar-edicao").classList.add("oculto");
  }

  let temporizadorBusca;
  $("busca-cliente").addEventListener("input", () => {
    clearTimeout(temporizadorBusca);
    temporizadorBusca = setTimeout(carregarClientes, 300);
  });

  $("tabela-clientes").addEventListener("click", (evento) => {
    const botao = evento.target.closest("[data-editar]");
    if (!botao) return;
    const cliente = estado.clientes.find((c) => c.id === Number(botao.dataset.editar));
    estado.clienteEditado = cliente.id;
    $("cliente-nome").value = cliente.nome;
    $("cliente-cpf").value = cliente.cpf || "";
    $("cliente-telefone").value = cliente.telefone;
    $("cliente-credor").value = cliente.credor;
    $("cliente-valor").value = cliente.valor_divida.toFixed(2);
    $("cliente-vencimento").value = cliente.data_vencimento;
    $("titulo-cliente").textContent = `Editando ${cliente.nome}`;
    $("cancelar-edicao").classList.remove("oculto");
    $("link-gerado").classList.add("oculto");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  $("cancelar-edicao").addEventListener("click", limparFormularioCliente);

  $("formulario-cliente").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const dados = {
      nome: $("cliente-nome").value,
      cpf: $("cliente-cpf").value,
      telefone: $("cliente-telefone").value,
      credor: $("cliente-credor").value,
      valor_divida: $("cliente-valor").value,
      data_vencimento: $("cliente-vencimento").value,
    };
    try {
      const cliente = estado.clienteEditado
        ? await Comum.api(`/api/admin/clientes/${estado.clienteEditado}`, { method: "PUT", body: dados })
        : await Comum.api("/api/admin/clientes", { method: "POST", body: dados });
      limparFormularioCliente();
      const link = $("link-gerado");
      link.innerHTML = `<span>Link de atendimento: <strong>${Comum.escapar(cliente.link)}</strong></span>
        <button type="button" class="botao botao-secundario" data-copiar="${Comum.escapar(cliente.link)}">Copiar</button>`;
      link.classList.remove("oculto");
      carregarClientes();
    } catch (erro) {
      Comum.avisar(erro.message);
    }
  });

  async function carregarConversas() {
    const parametros = new URLSearchParams({
      busca: $("filtro-busca").value.trim(),
      status: $("filtro-status").value,
      data_inicio: $("filtro-inicio").value,
      data_fim: $("filtro-fim").value,
      pagina: estado.pagina,
    });
    let resultado;
    try {
      resultado = await Comum.api(`/api/atendimento/historico?${parametros}`);
    } catch (erro) {
      return Comum.avisar(erro.message);
    }
    estado.paginas = resultado.paginas;
    $("info-pagina").textContent = `Página ${resultado.pagina} de ${resultado.paginas} · ${resultado.total} conversa(s)`;
    $("pagina-anterior").disabled = resultado.pagina <= 1;
    $("pagina-seguinte").disabled = resultado.pagina >= resultado.paginas;
    if (!resultado.itens.length) {
      $("tabela-conversas").innerHTML = '<tr><td colspan="9" class="texto-suave">Nenhuma conversa encontrada.</td></tr>';
      return;
    }
    $("tabela-conversas").innerHTML = resultado.itens
      .map(
        (conversa) => `
        <tr>
          <td>${conversa.id}</td>
          <td>${Comum.formatarHorario(conversa.iniciada_em)}</td>
          <td>${Comum.escapar(conversa.cliente.nome)}<br><small class="texto-suave">${Comum.formatarTelefone(conversa.cliente.telefone)}</small></td>
          <td>${Comum.escapar(conversa.cliente.credor)}</td>
          <td>${Comum.escapar(conversa.assunto || "-")}</td>
          <td>${Comum.escapar(conversa.operador ? conversa.operador.nome : "-")}</td>
          <td><span class="etiqueta etiqueta-${conversa.status}">${rotulosStatus[conversa.status]}</span></td>
          <td>${Comum.formatarData(conversa.retencao_ate)}</td>
          <td><button type="button" class="botao botao-secundario" data-ver="${conversa.id}">Ver</button></td>
        </tr>`
      )
      .join("");
  }

  $("filtro-conversas").addEventListener("submit", (evento) => {
    evento.preventDefault();
    estado.pagina = 1;
    carregarConversas();
  });
  $("pagina-anterior").addEventListener("click", () => {
    estado.pagina = Math.max(1, estado.pagina - 1);
    carregarConversas();
  });
  $("pagina-seguinte").addEventListener("click", () => {
    estado.pagina = Math.min(estado.paginas, estado.pagina + 1);
    carregarConversas();
  });

  const anexos = new Map();
  async function urlAnexo(anexo) {
    if (!anexos.has(anexo.id)) {
      const blob = await Comum.api(`/api/atendimento/anexos/${anexo.id}`, { binario: true });
      anexos.set(anexo.id, URL.createObjectURL(blob));
    }
    return anexos.get(anexo.id);
  }

  $("tabela-conversas").addEventListener("click", async (evento) => {
    const botao = evento.target.closest("[data-ver]");
    if (!botao) return;
    let dados;
    try {
      dados = await Comum.api(`/api/atendimento/conversas/${botao.dataset.ver}`);
    } catch (erro) {
      return Comum.avisar(erro.message);
    }
    const { conversa, mensagens } = dados;
    $("conversa-titulo").textContent = `Conversa nº ${conversa.id} · ${conversa.cliente.nome}`;
    $("conversa-detalhes").textContent = `${conversa.cliente.credor} · ${Comum.formatarTelefone(conversa.cliente.telefone)} · ${
      rotulosStatus[conversa.status]
    } · Guardar até ${Comum.formatarData(conversa.retencao_ate)}`;
    const lista = $("conversa-mensagens");
    lista.innerHTML = "";
    const opcoes = { perspectiva: "operador", mostrarOperador: true, credor: conversa.cliente.credor, urlAnexo };
    mensagens.forEach((mensagem) => lista.appendChild(Comum.criarMensagem(mensagem, opcoes)));
    $("modal-conversa").classList.remove("oculto");
  });

  $("fechar-conversa").addEventListener("click", () => $("modal-conversa").classList.add("oculto"));

  carregarOperadores();
})();
