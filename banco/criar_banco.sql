IF DB_ID(N'MJChat') IS NULL
    CREATE DATABASE MJChat COLLATE Latin1_General_CI_AI;
GO

USE MJChat;
GO

IF OBJECT_ID(N'dbo.usuarios', N'U') IS NULL
CREATE TABLE dbo.usuarios (
    id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_usuarios PRIMARY KEY,
    matricula VARCHAR(4) NOT NULL CONSTRAINT uq_usuarios_matricula UNIQUE,
    nome NVARCHAR(120) NOT NULL,
    senha_hash VARCHAR(100) NOT NULL,
    perfil VARCHAR(20) NOT NULL CONSTRAINT df_usuarios_perfil DEFAULT 'operador',
    ativo BIT NOT NULL CONSTRAINT df_usuarios_ativo DEFAULT 1,
    criado_em DATETIME2(0) NOT NULL CONSTRAINT df_usuarios_criado_em DEFAULT SYSDATETIME(),
    ultimo_acesso DATETIME2(0) NULL,
    CONSTRAINT ck_usuarios_matricula CHECK (matricula LIKE '[0-9][0-9][0-9][0-9]'),
    CONSTRAINT ck_usuarios_perfil CHECK (perfil IN ('admin', 'operador'))
);
GO

IF OBJECT_ID(N'dbo.clientes', N'U') IS NULL
CREATE TABLE dbo.clientes (
    id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_clientes PRIMARY KEY,
    nome NVARCHAR(150) NOT NULL,
    cpf VARCHAR(14) NULL,
    telefone VARCHAR(20) NOT NULL,
    credor NVARCHAR(150) NOT NULL,
    valor_divida NUMERIC(12,2) NOT NULL,
    data_vencimento DATE NOT NULL,
    token VARCHAR(64) NOT NULL CONSTRAINT uq_clientes_token UNIQUE,
    criado_em DATETIME2(0) NOT NULL CONSTRAINT df_clientes_criado_em DEFAULT SYSDATETIME(),
    atualizado_em DATETIME2(0) NOT NULL CONSTRAINT df_clientes_atualizado_em DEFAULT SYSDATETIME()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_clientes_telefone')
    CREATE INDEX ix_clientes_telefone ON dbo.clientes (telefone);
GO

IF OBJECT_ID(N'dbo.conversas', N'U') IS NULL
CREATE TABLE dbo.conversas (
    id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_conversas PRIMARY KEY,
    cliente_id INT NOT NULL CONSTRAINT fk_conversas_clientes REFERENCES dbo.clientes (id),
    operador_id INT NULL CONSTRAINT fk_conversas_usuarios REFERENCES dbo.usuarios (id),
    status VARCHAR(20) NOT NULL CONSTRAINT df_conversas_status DEFAULT 'iniciada',
    assunto NVARCHAR(500) NULL,
    iniciada_em DATETIME2(0) NOT NULL CONSTRAINT df_conversas_iniciada_em DEFAULT SYSDATETIME(),
    assumida_em DATETIME2(0) NULL,
    encerrada_em DATETIME2(0) NULL,
    ultima_mensagem_em DATETIME2(0) NOT NULL CONSTRAINT df_conversas_ultima DEFAULT SYSDATETIME(),
    retencao_ate DATE NOT NULL,
    CONSTRAINT ck_conversas_status CHECK (status IN ('iniciada', 'aguardando', 'em_atendimento', 'encerrada'))
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_conversas_cliente_id')
    CREATE INDEX ix_conversas_cliente_id ON dbo.conversas (cliente_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_conversas_operador_id')
    CREATE INDEX ix_conversas_operador_id ON dbo.conversas (operador_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_conversas_status')
    CREATE INDEX ix_conversas_status ON dbo.conversas (status);
GO

IF OBJECT_ID(N'dbo.mensagens', N'U') IS NULL
CREATE TABLE dbo.mensagens (
    id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_mensagens PRIMARY KEY,
    conversa_id INT NOT NULL CONSTRAINT fk_mensagens_conversas REFERENCES dbo.conversas (id),
    remetente VARCHAR(20) NOT NULL,
    usuario_id INT NULL CONSTRAINT fk_mensagens_usuarios REFERENCES dbo.usuarios (id),
    tipo VARCHAR(20) NOT NULL CONSTRAINT df_mensagens_tipo DEFAULT 'texto',
    conteudo NVARCHAR(MAX) NULL,
    url_boleto VARCHAR(2000) NULL,
    valor_boleto NUMERIC(12,2) NULL,
    vencimento_boleto DATE NULL,
    enviada_em DATETIME2(0) NOT NULL CONSTRAINT df_mensagens_enviada_em DEFAULT SYSDATETIME(),
    CONSTRAINT ck_mensagens_remetente CHECK (remetente IN ('cliente', 'operador', 'sistema')),
    CONSTRAINT ck_mensagens_tipo CHECK (tipo IN ('texto', 'anexo', 'boleto'))
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_mensagens_conversa_id')
    CREATE INDEX ix_mensagens_conversa_id ON dbo.mensagens (conversa_id);
GO

IF OBJECT_ID(N'dbo.anexos', N'U') IS NULL
CREATE TABLE dbo.anexos (
    id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_anexos PRIMARY KEY,
    mensagem_id INT NOT NULL CONSTRAINT fk_anexos_mensagens REFERENCES dbo.mensagens (id)
        CONSTRAINT uq_anexos_mensagem UNIQUE,
    nome_arquivo NVARCHAR(255) NOT NULL,
    tipo_mime VARCHAR(100) NOT NULL,
    tamanho INT NOT NULL,
    dados VARBINARY(MAX) NOT NULL
);
GO

CREATE OR ALTER TRIGGER dbo.tr_conversas_retencao ON dbo.conversas
INSTEAD OF DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE retencao_ate > CAST(SYSDATETIME() AS DATE))
        THROW 50001, N'Conversas devem ser mantidas por 5 anos (prazo legal de retenção).', 1;
    DELETE c FROM dbo.conversas c INNER JOIN deleted d ON d.id = c.id;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_mensagens_retencao ON dbo.mensagens
INSTEAD OF DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM deleted d
        INNER JOIN dbo.conversas c ON c.id = d.conversa_id
        WHERE c.retencao_ate > CAST(SYSDATETIME() AS DATE)
    )
        THROW 50002, N'Mensagens devem ser mantidas por 5 anos (prazo legal de retenção).', 1;
    DELETE m FROM dbo.mensagens m INNER JOIN deleted d ON d.id = m.id;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_mensagens_imutaveis ON dbo.mensagens
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    THROW 50003, N'Mensagens registradas não podem ser alteradas.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_anexos_retencao ON dbo.anexos
INSTEAD OF DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM deleted d
        INNER JOIN dbo.mensagens m ON m.id = d.mensagem_id
        INNER JOIN dbo.conversas c ON c.id = m.conversa_id
        WHERE c.retencao_ate > CAST(SYSDATETIME() AS DATE)
    )
        THROW 50004, N'Anexos devem ser mantidos por 5 anos (prazo legal de retenção).', 1;
    DELETE a FROM dbo.anexos a INNER JOIN deleted d ON d.id = a.id;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_anexos_imutaveis ON dbo.anexos
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    THROW 50005, N'Anexos registrados não podem ser alterados.', 1;
END;
GO
