# iPhyloGeo Backend

FastAPI backend for the iPhyloGeo phylogeography application.

## Prerequisites

- Python 3.10
- Docker Desktop (for MongoDB and Redis)
- Git

## Local development setup

### 1. Clone the repository

```bash
git clone https://github.com/tahiri-lab/iPhyloGeo
cd iPhyloGeo-backend
```

### 2. Create the environment file

```bash
cp .env.example .env
```

The defaults in `.env.example` match the Docker ports used below. Edit `EMAIL_USER` and `EMAIL_PASSWORD` if you need email functionality.

### 3. Create and activate a Python 3.10 virtual environment

**macOS / Linux**
```bash
python3.10 -m venv venv
source venv/bin/activate
```

**Windows**
```bat
py -3.10 -m venv venv
venv\Scripts\activate
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the database services

Run only the infrastructure containers (MongoDB and Redis). The API and worker run locally.

```bash
docker compose up -d mongo redis
```

### 6. Install alignment tool binaries (optional)

These are only required if you use MUSCLE, MAFFT, ClustalW, or FastTree alignment methods. You can skip this step and the core API will still work.

The binary location depends on the platform:

**macOS and Linux** — place binaries in `aphylogeo/bin/` inside the project root (gitignored):

```
aphylogeo/bin/
    muscle5.1.linux_intel64
    FastTree
    clustalw2
    mafft-linux64/
        mafft.bat
        mafftdir/
            bin/
            libexec/
    tmp/
```

| Tool | Download |
|---|---|
| MUSCLE 5 | https://drive5.com/muscle/downloads_v5.htm — pick `muscle-osx-arm64` (macOS ARM), `muscle-osx-x86` (macOS Intel), or `muscle-linux-x86`. Rename the file to `muscle5.1.linux_intel64` and run `chmod +x`. |
| FastTree | No prebuilt macOS binary. Compile with: `gcc -O3 -funsafe-math-optimizations -march=native -o aphylogeo/bin/FastTree FastTree.c -lm` after downloading `FastTree.c` from http://www.microbesonline.org/fasttree/. On Linux a prebuilt binary is available on the same page. |
| MAFFT | https://mafft.cbrc.jp/alignment/software/ — download the macOS or Linux package and place its contents under `aphylogeo/bin/mafft-linux64/`. |
| ClustalW2 | http://www.clustal.org/clustal2/ — download the macOS or Linux binary, name it `clustalw2`, and run `chmod +x`. |

Create the required tmp directory:

```bash
mkdir -p aphylogeo/bin/tmp
```

**Windows** — place binaries in `venv\Lib\site-packages\aphylogeo\bin\` (aphylogeo resolves an absolute path into the venv on Windows):

```
venv\Lib\site-packages\aphylogeo\bin\
    muscle5.1.win64.exe
    clustalw2.exe
    FastTree.exe
    mafft-win\
        mafft.bat
    tmp\
```

| Tool | Download |
|---|---|
| MUSCLE 5 | https://drive5.com/muscle/downloads_v5.htm — `muscle-win64.exe`, rename to `muscle5.1.win64.exe` |
| FastTree | http://www.microbesonline.org/fasttree/#Install — Windows executable |
| MAFFT | https://mafft.cbrc.jp/alignment/software/windows.html — extract the `mafft-win/` folder |
| ClustalW2 | http://www.clustal.org/clustal2/ — `clustalw2.exe` |

### 7. Run the backend

Open two terminals with the virtual environment activated.

**Terminal 1 — API**
```bash
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Worker**
```bash
python worker.py
```

The API will be available at http://localhost:8000 and the interactive docs at http://localhost:8000/docs.

## Docker deployment

To build and run the full stack with Docker (API, worker, MongoDB, Redis):

```bash
docker compose up
```

The Dockerfile installs `fasttree`, `mafft`, and `clustalw` via apt, so no manual binary setup is needed for the containerized deployment. The `aphylogeo/` directory is excluded from the Docker build via `.dockerignore`.
