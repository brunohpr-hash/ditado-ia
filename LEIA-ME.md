# 🎙️ Ditado IA

Ditado universal com correção por inteligência artificial — fale em qualquer
lugar do Windows e o texto aparece corrigido onde o cursor estiver.

## Como funciona

1. **Segure `Alt+V`** (ou o atalho que você configurar)
2. **Fale** — português, inglês, espanhol, misturado... ele detecta sozinho
3. **Solte a tecla** — em 1-2 segundos o texto aparece digitado, já corrigido:
   sem "ééé", sem muletas, sem resmungos, com gramática e pontuação certas

## Instalação (3 passos)

1. **Instale o Python** (se ainda não tiver): https://www.python.org/downloads/
   ⚠️ Marque **"Add Python to PATH"** na instalação!
2. **Dê dois cliques em `instalar.bat`**
3. Na primeira execução, a tela de configurações abre:
   - Cole sua **chave de API do Groq** (gratuita): https://console.groq.com/keys
   - Confira o atalho e clique em **Salvar**

Pronto! O ícone azul de microfone fica na bandeja (perto do relógio) e o app
inicia junto com o Windows.

## Como abrir e fixar na barra de tarefas

Depois de instalar, você tem 3 jeitos de abrir o app:

- **Atalho "Ditado IA" na área de trabalho** (criado pelo instalador)
- Duplo clique em **`iniciar.bat`** na pasta do app
- Reiniciar o Windows (ele abre sozinho)

**Pra fixar na barra de tarefas:** arrasta o atalho "Ditado IA" da área de
trabalho até a barra de tarefas — ou clica nele com o botão direito →
"Fixar na barra de tarefas". Aí é 1 clique pra abrir sempre que precisar.

> O app roda silencioso na bandeja (ícone azul de microfone, perto do relógio).
> Se não aparecer, clique na setinha ^ da bandeja — e dá pra arrastar o ícone
> pra fora da setinha pra ele ficar sempre visível.

## Recursos

| Recurso | Descrição |
|---|---|
| 🎹 Atalho configurável | Padrão Alt+V; mude em Configurações → "Detectar" |
| 🤖 Correção por IA | 3 níveis: leve / normal / formal |
| 🌍 Multilíngue | Detecta o idioma automaticamente, até misturado |
| 📜 Histórico | Todas as transcrições salvas; duplo clique copia |
| 📴 Modo offline | Sem internet? O áudio fica guardado em "pendentes" para transcrever depois |
| 🔔 Sons | Bip agudo = gravando; bip grave = processando |

## Dicas

- **Nível "leve"**: quase não mexe no teu texto, só tira muletas óbvias
- **Nível "normal"** (padrão): texto limpo e natural, estilo Speakly
- **Nível "formal"**: pra e-mails e documentos profissionais
- Se o app não digitar em algum programa (raro), mude "Inserir texto via"
  para `type` nas configurações

## Custos

A camada gratuita do Groq cobre uso pessoal com folga (horas de áudio por dia).
Nenhum dado fica em servidor nosso — o áudio vai direto do teu PC pra API.
