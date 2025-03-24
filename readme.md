# 📺 Sistema de Gestão de Conteúdos para TVs

## 🇵🇹 Português

### 🎯 Descrição

Sistema web para gestão e apresentação de conteúdos multimédia (imagens e vídeos) em TVs de salas de reunião, com configurações personalizáveis e integração com NAS.

### ⚙️ Funcionalidades

- 📁 Upload manual de imagens e vídeos.
- 🔄 Importação automática a partir de uma NAS.
- 🖥️ Gestão de conteúdos por TV.
- 🎞️ Pré-visualização em tempo real das apresentações.
- 🧩 Plugins ativáveis: Relógio, Clima, Mensagens personalizadas e Som.
- 🆘 Fallback automático com imagem e logotipo personalizados.

### 🛠️ Tecnologias

- Flask (Python)
- SQLite
- HTML5, CSS3, JavaScript
- Bootstrap 5

### 🚀 Instalação

```bash
git clone https://github.com/teu-usuario/nome-do-repositorio.git
cd nome-do-repositorio

python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

pip install -r requirements.txt

python app.py
```

Aceder em:  
http://localhost:5000

### 🔐 Login Padrão

- **Utilizador:** admin
- **Senha:** password123

(Pode ser alterado na secção de "Configurações" do painel)

### 📂 Estrutura de Pastas

```
/static/uploads/          Uploads por TV
/static/defaults/         Imagens padrão (fallback)
/templates/               Templates HTML
/db/database.db           Base de dados SQLite
app.py                    Aplicação Flask principal
```

---

## 🇬🇧 English

### 🎯 Description

Web system for managing and displaying multimedia content (images and videos) on meeting room TVs, with customizable settings and NAS integration.

### ⚙️ Features

- Manual upload of images and videos.
- Automatic import from NAS.
- Manage content per TV.
- Real-time preview for each TV.
- Enable plugins like Clock, Weather, Custom Messages, and Sound.
- Automatic fallback with custom image and logo.

### 🛠️ Technologies

- Flask (Python)
- SQLite
- HTML5, CSS3, JavaScript
- Bootstrap 5

### 🚀 Installation

```bash
git clone https://github.com/your-username/repository-name.git
cd repository-name

python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

pip install -r requirements.txt

python app.py
```

Access at:  
http://localhost:5000

### 🔐 Default Login

- **User:** admin
- **Password:** password123

(Credentials can be updated from the "Settings" section in the admin panel)

### 📂 Folder Structure

```
/static/uploads/          Per-TV uploads
/static/defaults/         Fallback images
/templates/               HTML templates
/db/database.db           SQLite database
app.py                    Main Flask app
```

---

### ✨ Sugestões

- Melhorar suporte para múltiplos idiomas.
- Adicionar autenticação com níveis de permissão (admin/editor).
- Exportação de logs de atividades.

---

Feito com ❤️ em Flask.