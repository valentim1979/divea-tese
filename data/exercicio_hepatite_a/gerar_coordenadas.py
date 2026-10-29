"""Gera coordenadas fictícias para o exercício de hepatite A (dados fictícios).

Os seis setores (A a F) formam uma grade de 3 x 2 quarteirões de 300 m ao
redor do ponto central informado:

    A  B  C
    F  E  D

Assim o setor C fica vizinho de B e de D, como pede o cenário. Cada caso
recebe um ponto aleatório (semente fixa) dentro do seu setor.

Uso:
    python gerar_coordenadas.py --lat -23.42 --lon -51.93

Saídas (na mesma pasta):
    casos_SE_1-3.csv, casos_SE_4-5.csv, casos_SE_6-8.csv  -> uma camada cada
    pontos_interesse.csv
    setores_wkt.csv                                       -> polígonos A a F
"""
import argparse
import csv
import math
import random
from pathlib import Path

PASTA = Path(__file__).resolve().parent
LADO_M = 300      # lado de cada setor, em metros
MARGEM_M = 30     # distância mínima do ponto até a borda do setor

# (coluna, linha) de cada setor na grade; linha 0 = norte
GRADE = {"A": (0, 0), "B": (1, 0), "C": (2, 0), "F": (0, 1), "E": (1, 1), "D": (2, 1)}

# Posição fixa dos pontos de interesse dentro do setor (fração de 0 a 1)
POSICAO_PI = {"P1": (0.5, 0.5), "P2": (0.8, 0.5), "P3": (0.3, 0.3), "P4": (0.5, 0.5), "P5": (0.5, 0.6)}


def conversor(lat0, lon0):
    """Converte metros (x leste, y norte) a partir do centro em lat/lon."""
    m_lat = 1 / 111_320
    m_lon = 1 / (111_320 * math.cos(math.radians(lat0)))
    return lambda x, y: (round(lat0 + y * m_lat, 6), round(lon0 + x * m_lon, 6))


def origem_setor(setor):
    """Canto noroeste do setor, em metros a partir do centro da grade."""
    col, lin = GRADE[setor]
    return -1.5 * LADO_M + col * LADO_M, LADO_M - lin * LADO_M


def ponto(setor, fx, fy, para_latlon):
    x0, y0 = origem_setor(setor)
    util = LADO_M - 2 * MARGEM_M
    return para_latlon(x0 + MARGEM_M + fx * util, y0 - MARGEM_M - fy * util)


def ler(nome):
    with open(PASTA / nome, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def gravar(nome, linhas):
    with open(PASTA / nome, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lat", type=float, required=True, help="latitude do centro da área")
    p.add_argument("--lon", type=float, required=True, help="longitude do centro da área")
    p.add_argument("--semente", type=int, default=2026)
    args = p.parse_args()

    para_latlon = conversor(args.lat, args.lon)
    rnd = random.Random(args.semente)

    casos = ler("casos_hepatite_a_ficticios.csv")
    for c in casos:
        c["Latitude"], c["Longitude"] = ponto(c["Setor"], rnd.random(), rnd.random(), para_latlon)
    for camada in sorted({c["Camada"] for c in casos}):
        gravar(camada.replace("Casos SE ", "casos_SE_") + ".csv", [c for c in casos if c["Camada"] == camada])

    pontos = ler("pontos_interesse_ficticios.csv")
    for pi in pontos:
        pi["Latitude"], pi["Longitude"] = ponto(pi["Setor"], *POSICAO_PI[pi["Nome"]], para_latlon)
    gravar("pontos_interesse.csv", pontos)

    setores = []
    for setor in sorted(GRADE):
        x0, y0 = origem_setor(setor)
        cantos = [(x0, y0), (x0 + LADO_M, y0), (x0 + LADO_M, y0 - LADO_M), (x0, y0 - LADO_M), (x0, y0)]
        coords = ", ".join(f"{lon} {lat}" for lat, lon in (para_latlon(x, y) for x, y in cantos))
        setores.append({"WKT": f"POLYGON (({coords}))", "Nome": f"Setor {setor}"})
    gravar("setores_wkt.csv", setores)

    print(f"{len(casos)} casos, {len(pontos)} pontos de interesse e {len(setores)} setores gravados em {PASTA}")


if __name__ == "__main__":
    main()
