from flask import Flask, request, render_template_string, url_for
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


form_html = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8" />
    <title>Meeti Soluções</title>
    <link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css?family=Nunito:400,600&display=swap" rel="stylesheet">
    <link rel="icon" href="{{ url_for('static', filename='logo-meeti.jpg') }}" type="image/x-icon">
    <style>
        :root {
            --primary: #276ef1;
            --primary-dark: #155ab6;
            --secondary: #44bbee;
            --accent: #e0f7fa;
            --gray-900: #191f2e;
            --bg-card: rgba(255,255,255,0.93); /* Praticamente branco, quase nada translúcido */
            --font: #1e293b;
            --shadow: 0 14px 40px #b0c7ea66,0 2px 20px #badaff30;
            --radius: 21px;
        }
        html.dark {
            --bg-main: #141925;
            --bg-card: rgba(35, 41, 58, 0.93);
            --font: #e7eafd;
        }
        body {
            font-family: 'Nunito', Arial, sans-serif;
            background: #d9ebff url('{{ url_for('static', filename='dia.jpg') }}') no-repeat center center fixed;
            background-size: cover;
            min-height: 100vh;
            margin: 0;
            padding: 0;
            position: relative;
            overflow-x: hidden;
            background-color: var(--bg-main, #d9ebff);
            color: var(--font);
            transition: background 0.5s, color 0.3s;
        }
        html.dark body {
            background: #141925 url('{{ url_for('static', filename='noite.jpg') }}') no-repeat center center fixed;
            background-size: cover;
        }
        #loading-spinner { display: none; text-align: center; margin-top: 8px; }
        html.dark #loading-spinner span { color: #b4caf3; }
        .topbar {width:100%;background:none;padding-top:38px;padding-bottom:12px;display:flex;justify-content:center;align-items:center;position:relative;}
        .brand-logo-wrap {display:flex;flex-direction:column;align-items:center;flex:1 0 0;justify-content:center;}
        .brand-logo {
            margin: 0 auto;
            max-width: 320px;
            width: 55vw;
            background:rgba(255,255,255,0.32);
            border-radius:12px;
            display:block;
            filter: drop-shadow(0 4px 16px #276efaa3);
        }
        .brand-subtitle {
            text-align: center;
            margin-top: 14px;
            color: #fff;
            font-family: 'Montserrat', Arial, sans-serif;
            font-weight: 700;
            font-size: 1.5em;
            letter-spacing: 0.015em;
            text-shadow: 0 2px 10px #1c295ad0, 0 1px 0 #2262c780;
            line-height: 1.12;
            padding: 16px 24px 12px 24px;
            border-radius: 18px;
            background: rgba(30,42,68, 0.29);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            display: inline-block;
            box-shadow: 0 6px 32px #1c295a3c, 0 1.5px 0 #2262c744;
            max-width: 95vw;
        }
        html.dark .brand-subtitle {
            background: rgba(70,80,115,0.34);
            color: #fff;
            text-shadow: 0 2px 14px #101a3db0, 0 1.5px 0 #0d71c920;
        }
        .brand-contact-link {
            display: inline-block;
            margin-top: 14px;
            padding: 10px 34px;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size: 1.14em;
            font-weight: 700;
            color: #fff;
            border-radius: 14px;
            text-decoration: none;
            letter-spacing: 0.04em;
            background: rgba(30,42,68, 0.29);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            box-shadow: 0 4px 20px #1451ba3A;
            border: 1px solid rgba(132,171,222,0.22);
            transition: background .18s, filter .18s, border .16s;
            filter: drop-shadow(0 1px 16px #101e3f36);
        }
        .brand-contact-link:hover {
            background: rgba(70, 80, 150, 0.38);
            border: 1px solid rgba(97,144,227,0.25);
            filter: brightness(1.07) drop-shadow(0 3px 18px #155ab65A);
        }
        html.dark .brand-contact-link {
            background: rgba(70,80,115,0.33);
            color: #fff;
            border: 1px solid rgba(97,144,227,0.20);
        }
        .dark-toggle-btn {
            position:absolute;right:38px;top:40px;z-index:9;
            background: rgba(30,42,68, 0.29);
            color: white;
            border: none;
            outline: none;
            font-family: 'Montserrat',sans-serif;
            font-weight:600;
            font-size:1em;
            border-radius:12px;
            padding:7px 17px 7px 15px;
            cursor:pointer;
            box-shadow:0 3px 12px #0b295c60;
            letter-spacing:0.04em;
            opacity:1;
            transition:background .18s, filter .14s;
            filter: drop-shadow(0 2px 10px #11235528);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1.5px solid rgba(132,171,222,0.22);
        }
        .dark-toggle-btn:hover {
            background: rgba(70,80,150,0.38);
            filter: brightness(1.06) drop-shadow(0 3px 18px #155ab65A);
        }
        html.dark .dark-toggle-btn {
            background: rgba(65,70,105, 0.33);
            border: 1.5px solid rgba(97,144,227,0.14);
            color: #fff;
        }
        .footer-credit {
            position:fixed;
            left:28px;
            bottom:18px;
            z-index:99;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size:1.06em;
            font-weight: 700;
            color:#fff;
            opacity:0.98;
            letter-spacing:0.018em;
            text-shadow:0 1.5px 12px #0c164fbe, 0 2px 12px #44bbee33;
            user-select:none;
            pointer-events:none;
        }
        @media(max-width:600px) {
            .footer-credit {font-size:0.96em;left:8px;bottom:6px;}
        }
        .central-container {display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;width:100vw;}
        .container {
            max-width: 720px;
            min-width: 330px;
            width: 97vw;
            background: var(--bg-card);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            position: relative;
            margin: 44px auto;
            padding: 54px 38px 31px 38px;
        }
        .title-underline {width:78px;height:6px;background:linear-gradient(90deg,var(--primary) 0%,var(--secondary) 90%);margin:8px auto 0 auto;border-radius:9px;}
        h2 {text-align:center;color:#2b4971;margin-top:0.50em;margin-bottom:0.74em;font-family:'Montserrat', Arial, sans-serif;font-size:2em;font-weight:700;}
        html.dark h2 { color: #c4caef; }
        .motivation {text-align:center;color:#276ef1;font-size:1.10em;font-weight:600;font-family:'Montserrat',Arial,sans-serif;margin:-17px 0 38px 0;}
        html.dark .motivation { color: #b4caf3; }
        label {font-weight:600;color:#243a5e;margin-top:14px; font-size:1.13em;}
        html.dark label { color: #b7cfff;}
        input[type="text"], textarea, select {
            width: 100%;padding: 12px;border: 1.7px solid #b4cae9;
            border-radius: 8px;margin-top: 9px;margin-bottom: 12px;font-size: 1.13em;background: #f8fbfe;transition: border 0.15s, box-shadow 0.20s, background 0.20s, color 0.18s;font-family: 'Nunito', Arial, sans-serif; box-sizing: border-box; color: var(--font);}
        input[type="text"]:focus, textarea:focus, select:focus {border:1.7px solid var(--primary) !important;outline:none;box-shadow:0 0 0 2.5px #bfdfff77;}
        html.dark input[type="text"], html.dark textarea, html.dark select {background:#23293a;border-color:#375893;color:#e2e6fa;}
        select { min-height: 1px;}
        input[type="submit"] {width:100%;background:linear-gradient(93deg,var(--primary) 70%,var(--secondary) 200%);color:white;border:none;padding:14px 0;border-radius:10px;font-size:1.15em;font-family:"Montserrat",Arial,sans-serif;font-weight:bold;cursor:pointer;box-shadow:0 6px 23px #276ef11a, 0 2px 7px #2b497110;letter-spacing:0.10em;margin-top:8px;transition:background 0.18s, transform 0.13s, box-shadow 0.2s;outline:none;position:relative;}
        input[type="submit"]:hover {background:var(--primary-dark);}
        input[type="submit"]::after {content: ' 🔍';font-size:1.12em;line-height:1;margin-left:6px;opacity:0.75;}
        .result table {border-collapse: collapse;width: 100%;margin-top: 8px;font-size: 0.97em;background: white;border-radius: 10px;box-shadow: 0 2px 8px #b0c7ea17;}
        .result th, .result td {text-align: left;padding: 6px 8px;font-size: 1em;vertical-align: middle;border: none;}
        .result th {background: linear-gradient(90deg, #276ef1 60%, #44bbee 120%);color: #fff;font-weight: 800;letter-spacing: 0.01em;}
        .result td b.only-code {font-weight: 700;color: #1854b6;}
        html.dark .result table {background: #22294a;}
        html.dark .result th {background: linear-gradient(90deg, #28408a 30%, #1177dd 120%);color: #fff;}
        html.dark .result td {color: #e7eafd;background: #23273c;}
        html.dark .result td b.only-code {color: #fff !important;}
        html.dark .result tr:hover td {background: #23314e;}
        .result tr:hover td {background: #eaf5ff;}
        .error {margin-top: 36px;text-align: center;color: #c0392b;font-weight: bold;background: #ffeaea;border-radius: 13px;padding: 16px 1px 15px 1px;font-size: 1.08em;font-family: 'Montserrat', Arial, sans-serif;box-shadow: 0 1px 9px #90000022;}
        html.dark .error {background: #2a242b;color: #ff5151;box-shadow: 0 1px 7px #50103044;}
        .copy-codes-btn, .copy-full-btn {display: inline-block;padding: 7px 15px;margin: 13px 6px 0 0;font-size: 0.98em;background: linear-gradient(93deg,#276ef1 74%,#44bbee 104%);color: #fff;border: none;border-radius: 7px;cursor: pointer;font-family: 'Montserrat', sans-serif;font-weight: 600;transition: background 0.19s;}
        .copy-codes-btn:hover, .copy-full-btn:hover {background: #155ab6;}
    </style>
    <script>
        function toggleTheme() {
            document.documentElement.classList.toggle('dark');
            localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
        }
        window.onload = function() {
            if (localStorage.getItem('theme') === 'dark') {
                document.documentElement.classList.add('dark');
            }
            atualizarCamposCidadeEstado();
        }
        function mostraSpinner() {
            document.getElementById('loading-spinner').style.display = 'block';
        }
        function atualizarCamposCidadeEstado() {
            var cep = document.getElementById('cep').value.trim();
            var cidade = document.getElementById('cidade');
            var estado = document.getElementById('estado');
            var cepTemValor = cep.length > 0;
            cidade.disabled = cepTemValor;
            estado.disabled = cepTemValor;
            if (cepTemValor) {
                cidade.value = '';
                estado.selectedIndex = 0;
            }
        }
        document.addEventListener('DOMContentLoaded', function() {
            var cepInput = document.getElementById('cep');
            cepInput.addEventListener('input', atualizarCamposCidadeEstado);
            cepInput.addEventListener('change', atualizarCamposCidadeEstado);
        });
        function copiarTexto(texto, msgSucesso, msgErro) {
            if (!navigator.clipboard) {
                alert(msgErro); return;
            }
            navigator.clipboard.writeText(texto).then(function () {
                alert(msgSucesso);
            }, function () {
                alert(msgErro);
            });
        }
        // Copiar a coluna inteira do Código IBGE incluindo mensagens de erro
        function copiarCodigos() {
            var trs = document.querySelectorAll('#result-table tr');
            var codigos = [];
            for (var i = 1; i < trs.length; i++) { // pula cabeçalho
                var tds = trs[i].querySelectorAll('td');
                if (tds.length >= 3) {
                    codigos.push(tds[2].textContent.trim());
                }
            }
            if (codigos.length === 0) {
                alert('Nenhum código para copiar.');
                return;
            }
            copiarTexto(codigos.join('\\n'), 'Coluna "Código IBGE" copiada!', 'Erro ao copiar.');
        }
        function copiarCompleto() {
            var linhas = [];
            var trs = document.querySelectorAll('#result-table tr');
            for (var i = 1; i < trs.length; i++) {
                var tds = trs[i].querySelectorAll('td');
                if (tds.length >= 3) {
                    var cidade = tds[0].textContent.trim();
                    var uf = tds[1].textContent.trim();
                    var codigoOuErro = tds[2].textContent.trim();
                    linhas.push(cidade + '\\t' + uf + '\\t' + codigoOuErro);
                }
            }
            if (linhas.length === 0) {
                alert('Nenhum resultado para copiar.');
                return;
            }
            copiarTexto(linhas.join('\\n'), 'Resultados completos copiados!', 'Erro ao copiar resultados.');
        }
    </script>
</head>
<body>
    <div class="topbar">
        <span class="brand-logo-wrap">
            <img class="brand-logo" src="data:image/jpeg;base64,{{ logo_data }}" alt="Logo Meeti" />
            <div class="title-underline"></div>
            <div class="brand-subtitle">Encontre a solução perfeita para a sua empresa.</div>
            <a class="brand-contact-link" href="https://meetisolucoes.com.br/" target="_blank" rel="noopener">Entre em contato</a>
        </span>
        <button class="dark-toggle-btn" onclick="toggleTheme()" title="Alternar tema">🌓 Tema</button>
    </div>
    <div class="central-container">
        <div class="container">

            <div id="loading-spinner">
                <svg width="48" height="48" viewBox="0 0 48 48" style="margin:18px auto;display:block" xmlns="http://www.w3.org/2000/svg" fill="none">
                    <circle cx="24" cy="24" r="20" stroke="#276ef1" stroke-width="5" stroke-opacity="0.22"/>
                    <path d="M44 24a20 20 0 0 1-20 20" stroke="#276ef1" stroke-width="5" stroke-linecap="round">
                        <animateTransform attributeName="transform" type="rotate" from="0 24 24" to="360 24 24" dur="0.9s" repeatCount="indefinite"/>
                    </path>
                </svg>
                <span>Buscando informações...</span>
            </div>

            <h2>Consultar Código IBGE das Cidades</h2>
            <div class="motivation">Atualize seus cadastros de forma rápida e precisa</div>
            <form action="/consultar" method="post" onsubmit="mostraSpinner()">
                <label for="cep">Digite um ou mais CEPs (um por linha):</label>
                <textarea id="cep" name="cep" rows="4" placeholder="Exemplo: 12345678\n87654321">{{ cep|default('') }}</textarea>
                <label for="cidade">Digite uma ou mais cidades (um por linha):</label>
                <textarea id="cidade" name="cidade" rows="7" placeholder="Exemplo:\nFlorianópolis\nJoinville">{{ cidades|default('') }}</textarea>
                <label for="estado">Estado (UF) (opcional):</label>
                <select id="estado" name="estado">
                    <option value="" {% if not estado %}selected{% endif %}>-- Não informar --</option>
                    {% for uf in ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'] %}
                    <option value="{{ uf }}" {% if estado == uf %}selected{% endif %}>{{ uf }}</option>
                    {% endfor %}
                </select>
                <input type="submit" value="Consultar" />
            </form>
            {% if erro %}
            <div class="error">{{ erro }}</div>
            {% endif %}
            {% if resultados %}
            <div class="result">
                <h3>Resultados</h3>
                <table id="result-table">
                    <tr>
                        <th>Cidade</th>
                        <th>Estado</th>
                        <th>Código IBGE</th>
                    </tr>
                    {% for r in resultados %}
                        {% if r.codigo %}
                            <tr>
                                <td>{{ r.input }}</td>
                                <td>{{ r.uf }}</td>
                                <td><b class="only-code">{{ r.codigo }}</b></td>
                            </tr>
                        {% elif r.multiplos %}
                            {% for m in r.multiplos %}
                                <tr>
                                    <td>{{ m.nome }}</td>
                                    <td>{{ m.uf }}</td>
                                    <td><b class="only-code">{{ m.id }}</b></td>
                                </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td>{{ r.input }}</td>
                                <td>-</td>
                                <td style="color:#b94a4a;">{{ r.erro }}</td>
                            </tr>
                        {% endif %}
                    {% endfor %}
                </table>
                <button class="copy-codes-btn" onclick="copiarCodigos()">Copiar códigos IBGE</button>
                <button class="copy-full-btn" onclick="copiarCompleto()">Copiar resultado completo</button>
            </div>
            {% endif %}
        </div>
    </div>
    <span class="footer-credit">Criado por Ritcheli Gomes.</span>
</body>
</html>
"""


@app.route('/')
def index():
    logo = load_logo_base64()
    return render_template_string(form_html, logo_data=logo, estado='')


@app.route('/consultar', methods=['POST'])
def consultar():
    logo = load_logo_base64()
    cep_raw = request.form.get('cep', '')
    cidade_raw = request.form.get('cidade', '')
    estado = request.form.get('estado', '').upper() or None

    ceps = [re.sub(r'\D', '', c)
            for c in cep_raw.splitlines() if re.sub(r'\D', '', c)]
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
        return render_template_string(form_html, erro=erro, logo_data=logo, cep=cep_raw, cidades=cidade_raw, estado=estado or '')
    return render_template_string(form_html, resultados=resultados, logo_data=logo, cep='', cidades='', estado='')


if __name__ == '__main__':
    app.run(debug=True)
