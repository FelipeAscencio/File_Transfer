# Trabajo Práctico Nº1 'File Transfer'

## Materia: REDES (TA048)

## Grupo 1

### Integrantes:

| Alumno                  | Correo               | Padrón  |
|-------------------------|----------------------|---------|
| Ascencio Felipe Santino | fascencio@fi.uba.ar  | 110675  |
| Burgos Moreno Daniel    | dburgos@fi.uba.ar    | 110486  |
| García Pizales Ignacio  | igarciap@fi.uba.ar   | 105043  |
| Levi Dolores            | dolevi@fi.uba.ar     | 105993  |
| Orive María Sol         | morive@fi.uba.ar     | 91351   |

---

## Descripción

El propósito de esta aplicación es implementar un protocolo de **Transferencia Confiable de Datos (RDT)** utilizando **UDP** como protocolo de transporte.

Se desarrollaron dos versiones del protocolo:

- **Stop & Wait**
- **Selective Repeat**

Además, la aplicación permite forzar condiciones de error para validar la confiabilidad en la transferencia.

## Características de la implementación
- Operaciones soportadas:
  - `UPLOAD`: Envío de archivos del cliente al servidor.
  - `DOWNLOAD`: Descarga de archivos del servidor al cliente.
- Garantiza la entrega de paquetes con una pérdida de hasta **10%** en los enlaces.
- Manejo concurrente de múltiples clientes.
- Desarrollo en **Python**, siguiendo las especificaciones de **PEP8**.
- Control de errores:
  - `PAQUETES CORRUPTOS`: Verifica que no haya paquetes corruptos (Mediante 'Checksum').
  - `ARCHIVO INEXISTENTE`: Verifica que el archivo a subir por parte del 'Cliente' exista en la ruta correspondiente.
  - `CONTROL DE REQUEST DE CLIENTES DESCONECTADOS`: Si un 'Cliente' pierde la conexión, el 'Servidor' descarta la 'Request'.
  - `CONTROL DE REQUEST FALLIDAS`: Si una 'Request' no puede completarse, no necesariamente muere la conexión/interacción con el 'Cliente'.

## Requisitos

- Python 3.x instalado.
- Librería estándar `socket` de Python.
- Herramienta **Mininet** para simular condiciones de red.

## Instalar dependencias

Para instalar las dependencias necesarias para la ejecución tanto del 'Servidor', como del 'Cliente' y los 'Tests'. Simplemente basta con ejecutar por primera vez el 'Servidor' con el siguiente comando:

```bash
uv run src/start-server.py -r 0
```

## Ejecución de los tests

```bash
pytest
```

## Ejecución de la topología para probar casos con pérdida de paquetes

### Construir la topología en 'Mininet'

```bash
sudo mn --custom ./src/topology.py --topo customTopo,num_clients=2,loss_percent=10 --mac -x
```

Al hacer esto el 'host' debería estar conectado a '10.0.0.1:8080'.

### 'UPLOAD' con 'Stop & Wait'

#### Consola del 'Servidor'
```bash
python3 ./src/start-server.py -r 0 -H "10.0.0.1" -p 8080
```

#### Consola del 'Cliente'
```bash
python ./src/upload.py -n "hello_world.py" -r 0 -H "10.0.0.1" -p 8080
```

### 'DOWNLOAD' con 'Stop & Wait'

#### Consola del 'Servidor'
```bash
python3 ./src/start-server.py -r 0 H "10.0.0.1" -p 8080
```

#### Consola del 'Cliente'
```bash
python ./src/download.py -n "hello_world.py" -r 0 -H "10.0.0.1" -p 8080
```

### 'UPLOAD' con 'Selective Repeat'

#### Consola del 'Servidor'
```bash
python3 ./src/start-server.py -r 1 -H "10.0.0.1" -p 8080
```

#### Consola del 'Cliente'
```bash
python ./src/upload.py -n "hello_world.py" -r 1 -H "10.0.0.1" -p 8080
```

### 'DOWNLOAD' con 'Selective Repeat'

#### Consola del 'Servidor'
```bash
python3 ./src/start-server.py -r 1 H "10.0.0.1" -p 8080
```

#### Consola del 'Cliente'
```bash
python ./src/download.py -n "hello_world.py" -r 1 -H "10.0.0.1" -p 8080
```

## Comandos para la ejecución del 'Servidor'

```
> uv run src/start-server.py -r 1       # Inicia el servidor con el protocolo 'Selective Repeat'.

usage : uv run src/start-server.py [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [- s DIRPATH ] [ - r protocol ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host service IP address
-p , -- port service port
-s , -- storage storage dir path
-r , -- protocol error recovery protocol
```

## Comandos para 'Download' del 'Cliente'

```
> uv run src/download.py -n "hello_world.py" -d "src/my_folder" -p 8080 -H "127.0.0.1"       # Download del archivo 'hello_world.py' con el protocolo 'Stop & Wait'.

usage : uv run src/download.py [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ - d FILEPATH ] [ - n FILENAME ] [ - r
protocol ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host server IP address
-p , -- port server port
-d , -- dst destination file path
-n , -- name file name
-r , -- protocol error recovery protocol
```

## Comandos para 'Upload' del 'Cliente'

```
> uv run src/upload.py -n "hello_world.py" -r 0       # Hace el upload de archivo 'hello_world.py' con el protocolo 'Stop & Wait'.

usage : uv run src/upload.py [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ - s FILEPATH ] [ - n FILENAME ] [ - r
protocol ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host server IP address
-p , -- port server port
-s , -- src source file path
-n , -- name file name
-r , -- protocol error recovery protocol
```
