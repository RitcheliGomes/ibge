from flask import Flask, request, render_template, url_for
import requests
import unidecode
import base64
import os
import re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

municipios_cache = None
municipios_index = {}
cep_cache = {}

def carregar_municipios_cache():
    global municipios_cache, municipios_index
    if municipios_cache is None:
        try:
            resposta = requests.get(
                'https://servicodados.ibge.gov.br/api/v1/localidades/municipios', timeout=10)
            resposta.raise_for_status()
            municipios_cache = resposta.json()
            municipios_index.clear()
            for mun in municipios_cache:
                nome_norm = unidecode.unidecode(mun['nome']).lower()
                municipios_index.setdefault(nome_norm, []).append(mun)
        except requests.RequestException:
            municipios_cache = []
            municipios_index.clear()

def buscar_por_cep(cep):
    cep = re.sub(r'\D', '', cep or "")
    if len(cep) != 8:
        return None, None
    if cep in cep_cache:
        return cep_cache[cep]
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=3)
        dados = resp.json()
        if "erro" in dados:
            return None, None
        cidade = dados.get("localidade")
        uf = dados.get("uf")
        cep_cache[cep] = (cidade, uf)
        return cidade, uf
    except:
        return None, None

def multi_buscar_por_cep(ceps):
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(buscar_por_cep, cep) for cep in ceps]
        for cep, fut in zip(ceps, futures):
            cidade, uf = fut.result()
            results.append((cep, cidade, uf))
    return results

def load_logo_base64(path='logo_meeti.jpg'):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('ascii')
    return ""

def buscar_codigo_ibge(nome_cidade, sigla_uf=None):
    global municipios_cache, municipios_index
    if municipios_cache is None or not municipios_index:
        carregar_municipios_cache()
    nome_norm = unidecode.unidecode(nome_cidade).lower()
    candidatos = municipios_index.get(nome_norm, [])
    uf_req = sigla_uf.lower() if sigla_uf else None
    resultados = []
    for mun in candidatos:
        uf_mun = None
        micror = mun.get('microrregiao')
        if micror:
            meso = micror.get('mesorregiao')
            if meso and meso.get('UF') and 'sigla' in meso['UF']:
                uf_mun = meso['UF']['sigla'].lower()
        if uf_req and uf_req != uf_mun:
            continue
        if uf_req:
            return mun['id']
        resultados.append({
            'id': mun['id'],
            'nome': mun['nome'],
            'uf': uf_mun.upper() if uf_mun else ''
        })
    if uf_req:
        return None
    return resultados if resultados else None

def extrair_nome_uf(texto):
    m = re.match(r'^(.*?)[\s\\/\\-]+([A-Z]{2})$', texto.strip(), re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).upper()
    return texto.strip(), None

@app.route('/')
def index():
    logo = load_logo_base64()
    return render_template('index.html', logo_data=logo, estado='')

@app.route('/consultar', methods=['POST'])
def consultar():
    logo = load_logo_base64()
    cep_raw = request.form.get('cep', '')
    cidade_raw = request.form.get('cidade', '')
    estado = request.form.get('estado', '').upper() or None

    ceps = [re.sub(r'\D', '', c) for c in cep_raw.splitlines() if re.sub(r'\D', '', c)]
    cidades = [l.strip() for l in cidade_raw.splitlines() if l.strip()]

    resultados = []
    if ceps:
        ceps_resultados = multi_buscar_por_cep(ceps)
        for cep, cidade, uf in ceps_resultados:
            if not cidade or not uf:
                resultados.append(
                    {'input': f'CEP {cep}', 'erro': 'CEP não encontrado ou inválido.'})
                continue
            ibge = buscar_codigo_ibge(cidade, uf)
            if ibge:
                if isinstance(ibge, list):
                    resultados.append(
                        {'input': f'{cidade} {uf}', 'multiplos': ibge})
                else:
                    resultados.append(
                        {'input': cidade, 'uf': uf.upper(), 'codigo': ibge})
            else:
                resultados.append(
                    {'input': f'{cidade} {uf}', 'erro': 'Cidade ou IBGE não encontrado para esse CEP.'})
    if cidades and not ceps:
        for c in cidades:
            nome, uf_cidade = extrair_nome_uf(c)
            uf_final = uf_cidade if uf_cidade else (estado if estado else None)
            res = buscar_codigo_ibge(nome, uf_final)
            if res:
                if isinstance(res, list):
                    resultados.append({'input': c, 'multiplos': res})
                else:
                    resultados.append(
                        {'input': nome, 'uf': uf_final.upper() if uf_final else '', 'codigo': res})
            else:
                resultados.append(
                    {'input': c, 'erro': 'Cidade não encontrada'})
    if not resultados:
        erro = 'Por favor, informe ao menos um CEP ou uma cidade para consultar.'
        return render_template('index.html', erro=erro, logo_data=logo, cep=cep_raw, cidades=cidade_raw, estado=estado or '')
    return render_template('index.html', resultados=resultados, logo_data=logo, cep='', cidades='', estado='')

if __name__ == '__main__':
    app.run(debug=True)
