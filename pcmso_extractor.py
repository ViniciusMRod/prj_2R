#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║        EXTRATOR GENÉRICO PCMSO v2.0                                           ║
║        Programa de Controle Médico de Saúde Ocupacional                       ║
║                                                                                ║
║        Autor: Sistema de Extração de Dados                                    ║
║        Data: Janeiro 2026                                                     ║
║        Descrição: Extrai dados de múltiplos PDFs PCMSO e consolida em Excel   ║
║                                                                                ║
║        Funcionalidades:                                                       ║
║        • Leitura genérica de PDFs PCMSO (vários formatos)                     ║
║        • Extração de: Empresa, Cargos, Riscos, Exames                         ║
║        • Consolidação em Excel com 4 abas                                     ║
║        • Detecção robusta de riscos ocupacionais                              ║
║        • Tratamento de variações de layout                                    ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
"""

import pdfplumber
import pandas as pd
import re
import sys
from pathlib import Path
from datetime import datetime


class PCMSOExtractor:
    """
    Extrator genérico e robusto para documentos PCMSO.

    Características:
    - Suporta múltiplos formatos e layouts
    - Detecção flexível de campos
    - Tratamento de erros e variações
    - Consolidação de múltiplos documentos
    """

    # Mapeamento de tipos de risco
    TIPO_RISCO_MAP = {
        'ERGONÔMICO': [
            'BIOMECÂNICO', 'ERGONÔMICA', 'POSTURAS', 'MOVIMENTOS REPETITIVOS',
            'LEVANTAMENTO', 'FLEXÃO', 'COLUNA', 'LER/DORT', 'FORÇA'
        ],
        'MECÂNICO': [
            'QUEDA', 'ESCADA', 'OBJETOS', 'CORTES', 'PERFURAÇÃO',
            'PROJEÇÃO', 'INTEMPÉRIES', 'ACIDENTES DE TRÂNSITO'
        ],
        'ELÉTRICO': [
            'ENERGIA ELÉTRICA', 'RISCO ELÉTRICO', 'TENSÃO', 'ELÉTRICO'
        ],
        'ALTURA': [
            'TRABALHO EM ALTURA', 'QUEDA COM DIFERENÇA'
        ],
        'PSICOSSOCIAL': [
            'PSICOSSOCIAL', 'ESTRESSE', 'COGNITIVO'
        ]
    }

    def __init__(self, pdf_path):
        """Inicializa o extrator"""
        self.pdf_path = pdf_path
        self.pdf = pdfplumber.open(pdf_path)
        self.full_text = self._extract_full_text()
        self.metadata = {}
        self.empresa = {}
        self.cargos = []
        self.riscos = []
        self.exames = []

    def _filter_provider_header(self, text):
        """Remove cabeçalho da empresa prestadora (Prevenclínica)"""
        if not text:
            return ""
        lines = text.split('\n')
        filtered = []
        for line in lines:
            # Identificadores da Prevenclínica para remoção
            if ("43.453.808/0001-37" in line or 
                "supervisaosaoluis@prevenclinica.com.br" in line or
                ("Av. Colares Moreira" in line and "Renascença" in line) or
                line.strip() == "PCMSO - Programa de Controle Médico de Saúde Ocupacional"):
                continue
            filtered.append(line)
        return "\n".join(filtered)

    def _extract_full_text(self):
        """Extrai todo o texto do PDF filtrando cabeçalhos"""
        text = ""
        for page in self.pdf.pages:
            raw_text = page.extract_text() or ""
            text += self._filter_provider_header(raw_text) + "\n"
        return text

    def _clean_text(self, text):
        """Limpa e normaliza texto"""
        if not text:
            return ""
        text = text.strip().replace("\n", " ").replace("  ", " ")
        # Normaliza datas
        text = re.sub(r'(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})', r'\1/\2/\3', text)
        return text

    def extract_metadata(self):
        """Extrai metadados do arquivo"""
        path_obj = Path(self.pdf_path)
        stats = path_obj.stat()
        
        self.metadata = {
            'nome_arquivo': path_obj.name,
            'tamanho_kb': round(stats.st_size / 1024, 2),
            'data_modificacao': datetime.fromtimestamp(stats.st_mtime).strftime('%d/%m/%Y %H:%M:%S'),
            'numero_paginas': len(self.pdf.pages)
        }
        return self.metadata

    def extract_empresa(self):
        """Extrai dados da empresa com fallbacks robustos"""
        text = ""
        # Busca flexível pelo cabeçalho (considerando espaços e traços variados)
        header_pattern = re.compile(r'01\s*[-–]\s*Dados', re.IGNORECASE)

        for i, page in enumerate(self.pdf.pages):
            page_text = self._filter_provider_header(page.extract_text() or "")
            match = header_pattern.search(page_text)
            if match:
                text = page_text[match.start():]
                # Adiciona a próxima página se existir, para pegar dados quebrados
                if i + 1 < len(self.pdf.pages):
                    text += "\n" + self._filter_provider_header(self.pdf.pages[i+1].extract_text() or "")
                break

        # Fallback: Se não encontrar o cabeçalho, usa a primeira página
        if not text and len(self.pdf.pages) > 0:
            text = self._filter_provider_header(self.pdf.pages[0].extract_text() or "")

        # Razão Social
        match = re.search(r'Razão\s*social[:\s]+([^\n]+?)(?:Grau|CNPJ|$)', text, re.IGNORECASE)
        self.empresa['razao_social'] = self._clean_text(match.group(1)) if match else "N/A"

        # CNPJ
        match = re.search(r'CNPJ[:\s]*(\d{1,2}\.\d{1,3}\.\d{1,3}/\d{4}-\d{2})', text)
        self.empresa['cnpj'] = match.group(1) if match else "N/A"

        # Grau de Risco
        match = re.search(r'Grau\s+de\s+Risco[:\s]*(\d+)\s*\(([^)]+)\)', text, re.IGNORECASE)
        self.empresa['grau_risco'] = f"{match.group(1)} ({match.group(2)})" if match else "N/A"

        # Endereço
        match = re.search(r'Endereço[:\s]*([^\n]*?)(?=\s*CNPJ|\n|$)', text, re.IGNORECASE)
        self.empresa['endereco'] = self._clean_text(match.group(1))[:100] if match else "N/A"

        # DEBUG: Visualizar texto para CNAE
        # print("\n" + "="*50)
        # print("DEBUG: Texto para CNAE:")
        # print(text[:2000])
        # print("="*50 + "\n")

        # CNAE
        match = re.search(r'CNAE(?:.*?)([\d]{2}\.[\d]{2}-\d-\d{2})', text, re.IGNORECASE | re.DOTALL)
        self.empresa['cnae'] = match.group(1) if match else "N/A"

        # Número de profissionais
        match = re.search(r'[Nn]úmero(?:.*?)[:\s]+(\d+)', text)
        self.empresa['num_profissionais'] = match.group(1) if match else "N/A"

        # Responsável pela empresa
        match = re.search(r'[Rr]espons[áa]vel(?:.*?)[:\s]+([^\n]+?)(?:\n|$)', text)
        self.empresa['responsavel_empresa'] = self._clean_text(match.group(1)) if match else "N/A"

        # Médico PCMSO
        match = re.search(r'[Rr]esp\.?\s+PCMSO[:\s]+(?:Dr\.?\s+)?([^\n]+?)(?:CRM|$)', text)
        self.empresa['medico_pcmso'] = self._clean_text(match.group(1)) if match else "N/A"

        # # DEBUG: Visualizar o texto onde a busca está sendo feita
        # print("\n" + "="*50)
        # print("DEBUG: Texto extraído para busca de datas:")
        # print(text[:2000])
        # print("="*50 + "\n")

        # Vigência
        # Padrões para data de início (ordem de prioridade)
        patterns_inicio = [
            r'In.cio\s+(?:da\s+)?Validade[:\s]+(\d{1,2}[\s]+/\d{1,2}/\d{2,4})',
            r'In.cio\s+(?:da\s+)?Vig.ncia[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'Data\s+de\s+In.cio[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'Data\s+de\s+Emiss.o[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'Vig.ncia[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'Per.odo[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})'
        ]
        self.empresa['vigencia_inicio'] = "N/A"
        for p in patterns_inicio:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                self.empresa['vigencia_inicio'] = self._clean_text(match.group(1))
                break

        # Padrões para data de fim
        patterns_fim = [
            r'Fim\s+(?:da\s+)?Validade[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'Fim\s+(?:da\s+)?Vig.ncia[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'Revisar\s+at.[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
            r'V.lido\s+at.[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})'
        ]
        self.empresa['vigencia_fim'] = "N/A"
        for p in patterns_fim:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                self.empresa['vigencia_fim'] = self._clean_text(match.group(1))
                break

        return self.empresa

    def extract_cargos(self):
        """
        Extrai cargos de forma mais robusta:
        - Tenta primeiro via extração de TABELA (pdfplumber) para preservar estrutura.
        - Trata células mescladas (propaga setor) e quebras de linha dentro da célula.
        - Fallback para parsing textual se a tabela não for detectada.
        Output (mantido): lista de dicts {'setor': <str>, 'cargo': <str>}
        """
        def norm_cell(x: str) -> str:
            if x is None:
                return ""
            return re.sub(r"\s+", " ", str(x).replace("\n", " ")).strip()

        def looks_like_setor(s: str) -> bool:
            s_up = s.upper()
            return (
                bool(re.match(r"^EST\s*\d+", s_up)) or
                s_up.startswith(("SETOR", "LOCAL", "DEPARTAMENTO", "GHE")) or
                ("EST" in s_up and "-" in s_up)
            )

        def split_cargo_qty(text: str):
            """
            Se vier algo como 'GERENTE GERAL 01' ou '... (EXCETO ...) 00'
            retorna (cargo, qty|None)
            """
            m = re.match(r"^(.*?)(?:\s+(\d{1,3}))$", text.strip())
            if m:
                return m.group(1).strip(), m.group(2)
            return text.strip(), None

        def parse_rows_from_table(table_rows):
            cargos = []
            current_setor = ""

            for row in table_rows:
                cells = [norm_cell(c) for c in row if c is not None]
                # ignora linhas vazias
                if not any(cells):
                    continue

                row_text = " ".join([c for c in cells if c]).strip()

                # ignora header da tabela
                if "SETOR" in row_text.upper() and "CARGO" in row_text.upper():
                    continue

                # Heurística de colunas (idealmente 3: setor | cargos | qtd)
                # Mas alguns PDFs colapsam 2 colunas ou 1 coluna.
                if len(cells) >= 3:
                    setor_cell = cells[0]
                    cargo_cell = cells[1]
                    # qty_cell = cells[2]  # se quiser validar

                    # célula mesclada: setor vazio -> herda setor anterior
                    if setor_cell and looks_like_setor(setor_cell):
                        current_setor = setor_cell
                    elif not setor_cell and current_setor:
                        pass
                    elif setor_cell and not looks_like_setor(setor_cell) and current_setor:
                        # às vezes o "setor" vem grudado estranho; não troca
                        pass

                    cargo_clean, _ = split_cargo_qty(cargo_cell)
                    cargo_clean = cargo_clean.upper()

                    if current_setor and len(cargo_clean) > 3:
                        cargos.append({"setor": current_setor.strip(), "cargo": cargo_clean})
                    continue

                # Caso 2 colunas: setor | cargo(+qty)  OU setor pode vir vazio por mesclagem
                if len(cells) == 2:
                    a, b = cells[0], cells[1]

                    if looks_like_setor(a):
                        current_setor = a
                        cargo_clean, _ = split_cargo_qty(b)
                    else:
                        # setor mesclado -> a é cargo e b é qty OU a vazio
                        if a == "" and current_setor:
                            cargo_clean, _ = split_cargo_qty(b)
                        else:
                            # pode ser cargo na primeira e qty na segunda
                            cargo_clean = a

                    cargo_clean = norm_cell(cargo_clean).upper()
                    if current_setor and len(cargo_clean) > 3 and not cargo_clean.isdigit():
                        cargos.append({"setor": current_setor.strip(), "cargo": cargo_clean})
                    continue

                # Caso 1 coluna: "EST ... CARGO ... 01" ou apenas "CARGO 01" (setor mesclado)
                if len(cells) == 1:
                    s = cells[0]

                    # padrão colapsado: "EST 0001 - ADMINISTRATIVO GERENTE GERAL 01"
                    m = re.match(r"^(EST\s*\d+\s*-\s*.+?)\s+(.+?)\s+(\d{1,3})$", s, flags=re.IGNORECASE)
                    if m:
                        current_setor = norm_cell(m.group(1))
                        cargo_clean = norm_cell(m.group(2)).upper()
                        if len(cargo_clean) > 3:
                            cargos.append({"setor": current_setor.strip(), "cargo": cargo_clean})
                        continue

                    # se for setor sozinho (mesclado em várias linhas)
                    if looks_like_setor(s):
                        current_setor = s
                        continue

                    # se for cargo sozinho e já temos setor corrente
                    cargo_clean, _ = split_cargo_qty(s)
                    cargo_clean = norm_cell(cargo_clean).upper()
                    if current_setor and len(cargo_clean) > 3:
                        cargos.append({"setor": current_setor.strip(), "cargo": cargo_clean})
                    continue

            return cargos

        # -----------------------------
        # 1) localizar páginas do QUADRO DE CARGOS
        # -----------------------------
        pages_with_quadro = []
        for i, page in enumerate(self.pdf.pages):
            txt = self._filter_provider_header(page.extract_text() or "")
            if re.search(r"QUADRO\s+DE\s+CARGOS", txt, re.IGNORECASE):
                pages_with_quadro.append(i)

        # -----------------------------
        # 2) tentar extração por TABELA (mais fiel a mesclagens)
        # -----------------------------
        table_settings = {
            "vertical_strategy": "lines",      # tenta usar linhas quando existem
            "horizontal_strategy": "lines",
            "intersection_tolerance": 5,
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 20,
            "min_words_vertical": 1,
            "min_words_horizontal": 1,
            "text_tolerance": 2,
        }

        extracted = []
        for pno in pages_with_quadro:
            page = self.pdf.pages[pno]
            try:
                tables = page.extract_tables(table_settings=table_settings) or []
            except Exception:
                tables = []

            # às vezes o quadro “vaza” para a página seguinte
            if pno + 1 < len(self.pdf.pages):
                try:
                    tables += (self.pdf.pages[pno + 1].extract_tables(table_settings=table_settings) or [])
                except Exception:
                    pass

            for t in tables:
                # Heurística: tabelas pequenas demais raramente são o quadro de cargos
                if not t or len(t) < 2:
                    continue
                extracted.extend(parse_rows_from_table(t))

        # -----------------------------
        # 3) fallback para texto (se não veio nada via tabela)
        # -----------------------------
        if not extracted:
            text = self.full_text
            match = re.search(
                r"QUADRO\s+DE\s+CARGOS(.*?)(?:02\s*[-–]\s*APRESENTAÇÃO|HISTÓRICO|Ambiente|$)",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if match:
                cargo_text = match.group(1)
                lines = [l.strip() for l in cargo_text.split("\n") if l.strip()]
                current_setor = ""
                for line in lines:
                    if "SETOR" in line.upper() and "CARGOS" in line.upper():
                        continue
                    if looks_like_setor(line):
                        current_setor = line
                        continue

                    # tenta pegar "CARGO ... 01"
                    cargo_clean, _ = split_cargo_qty(line)
                    cargo_clean = cargo_clean.upper()

                    # evita falsos positivos
                    if current_setor and len(cargo_clean) > 3 and not cargo_clean.isdigit():
                        extracted.append({"setor": current_setor.strip(), "cargo": cargo_clean})

        # -----------------------------
        # 4) deduplicação e retorno (output igual ao atual)
        # -----------------------------
        seen = set()
        unique = []
        for c in extracted:
            key = (c["setor"], c["cargo"])
            if key not in seen:
                seen.add(key)
                unique.append(c)

        self.cargos = unique
        return self.cargos


    def extract_riscos(self):
        """Extrai riscos com classificação automática"""
        text = self.full_text

        pattern = r'Risco[:\s]+([^\n]+?)(?:\n|$)\s*(?:Danos?\s+(?:à|a)\s+)?[Ss]aúde[:\s]+([^\n]+?)(?:\n|RISCO|$)'

        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)

        for match in matches:
            risco_desc = self._clean_text(match.group(1))
            dano_desc = self._clean_text(match.group(2))

            # Classificar tipo de risco
            tipo = 'GERAL'
            for tipo_chave, palavras in self.TIPO_RISCO_MAP.items():
                if any(palavra in risco_desc.upper() for palavra in palavras):
                    tipo = tipo_chave
                    break

            if risco_desc and len(risco_desc) > 5:
                self.riscos.append({
                    'tipo': tipo,
                    'risco': risco_desc[:100],
                    'danos': dano_desc[:100] if dano_desc else "N/A"
                })

        # Remover duplicatas
        seen = set()
        unique = []
        for risco in self.riscos:
            key = (risco['tipo'], risco['risco'])
            if key not in seen:
                seen.add(key)
                unique.append(risco)

        self.riscos = unique
        return self.riscos

    def extract_exames(self):
        """Extrai exames com periodicidade"""
        text = self.full_text

        exame_patterns = {
            'Exame Clínico': r'Exame\s+Clínic[ao]',
            'Hemograma': r'Hemograma',
            'Glicemia': r'Glicemia',
            'ECG': r'ECG|Eletrocardiograma',
            'Radiografia de Coluna': r'Rx\s+de\s+Coluna|Radiografia.*Coluna',
            'Acuidade Visual': r'Acuidade\s+Visual|Teste\s+de\s+Visão',
            'Audiometria': r'Audiometria|Teste\s+Auditivo',
            'Espirometria': r'Espirometria|Teste\s+Respiratório',
        }

        for exame, pattern in exame_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                self.exames.append({
                    'exame': exame,
                    'periodicidade': 'Anual'
                })

        return self.exames

    def extract_all(self):
        """Extrai todos os dados"""
        self.extract_metadata()
        self.extract_empresa()
        self.extract_cargos()
        self.extract_riscos()
        self.extract_exames()

        return {
            'metadata': self.metadata,
            'empresa': self.empresa,
            'cargos': self.cargos,
            'riscos': self.riscos,
            'exames': self.exames
        }


def processar_pcmso(pdf_files):
    """Processa múltiplos PDFs PCMSO"""
    resultados = []

    for pdf_path in pdf_files:
        try:
            extrator = PCMSOExtractor(pdf_path)
            dados = extrator.extract_all()
            resultados.append(dados)
            extrator.pdf.close()
            print(f"✓ {Path(pdf_path).name}")
        except Exception as e:
            print(f"✗ {Path(pdf_path).name}: {str(e)[:50]}")

    return resultados


def consolidar_excel(resultados, output_path='PCMSO_Consolidado.xlsx'):
    """Consolida dados em Excel com 5 abas"""

    # Preparar dados
    metadata_data = []
    empresas_data = []
    cargos_data = []
    riscos_data = []
    exames_data = []

    for idx_empresa, dados in enumerate(resultados, 1):
        meta = dados.get('metadata', {}).copy()
        meta['id_arquivo'] = idx_empresa
        meta['id_empresa'] = idx_empresa
        # Adiciona razão social para facilitar identificação
        meta['razao_social_associada'] = dados['empresa'].get('razao_social', 'N/A')
        metadata_data.append(meta)

        emp = dados['empresa'].copy()
        emp['id_arquivo'] = idx_empresa
        emp['id_empresa'] = idx_empresa
        empresas_data.append(emp)

        for cargo in dados['cargos']:
            cargos_data.append({
                'id_empresa': idx_empresa,
                'razao_social': dados['empresa'].get('razao_social'),
                'setor': cargo.get('setor'),
                'cargo': cargo.get('cargo')
            })

        for risco in dados['riscos']:
            riscos_data.append({
                'id_empresa': idx_empresa,
                'razao_social': dados['empresa'].get('razao_social'),
                'tipo_risco': risco.get('tipo'),
                'descricao_risco': risco.get('risco'),
                'danos_saude': risco.get('danos')
            })

        for exame in dados['exames']:
            exames_data.append({
                'id_empresa': idx_empresa,
                'razao_social': dados['empresa'].get('razao_social'),
                'exame': exame.get('exame'),
                'periodicidade': exame.get('periodicidade')
            })

    # Criar DataFrames
    df_metadata = pd.DataFrame(metadata_data)
    # Reordenar colunas para id_arquivo ficar no início
    if not df_metadata.empty and 'id_arquivo' in df_metadata.columns:
        cols = ['id_arquivo'] + [c for c in df_metadata.columns if c != 'id_arquivo']
        df_metadata = df_metadata[cols]
    df_empresas = pd.DataFrame(empresas_data)
    # Reordenar colunas para id_arquivo ficar no início
    if not df_empresas.empty and 'id_arquivo' in df_empresas.columns:
        cols = ['id_arquivo'] + [c for c in df_empresas.columns if c != 'id_arquivo']
        df_empresas = df_empresas[cols]
    df_cargos = pd.DataFrame(cargos_data) if cargos_data else pd.DataFrame()
    df_riscos = pd.DataFrame(riscos_data) if riscos_data else pd.DataFrame()
    df_exames = pd.DataFrame(exames_data) if exames_data else pd.DataFrame()

    # Salvar Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_metadata.to_excel(writer, sheet_name='Metadados', index=False)
        df_empresas.to_excel(writer, sheet_name='Empresa', index=False)
        df_cargos.to_excel(writer, sheet_name='Cargos', index=False)
        df_riscos.to_excel(writer, sheet_name='Riscos', index=False)
        df_exames.to_excel(writer, sheet_name='Exames', index=False)

    # Salvar CSVs
    base_name = Path(output_path).stem
    df_metadata.to_csv(f"{base_name}_Metadados.csv", index=False, sep=';', encoding='utf-8-sig')
    df_empresas.to_csv(f"{base_name}_Empresa.csv", index=False, sep=';', encoding='utf-8-sig')
    df_cargos.to_csv(f"{base_name}_Cargos.csv", index=False, sep=';', encoding='utf-8-sig')
    df_riscos.to_csv(f"{base_name}_Riscos.csv", index=False, sep=';', encoding='utf-8-sig')
    df_exames.to_csv(f"{base_name}_Exames.csv", index=False, sep=';', encoding='utf-8-sig')

    return output_path


def main():
    """Função principal"""
    print("\n" + "="*80)
    print("EXTRATOR GENÉRICO PCMSO v2.0")
    print("="*80)

    # Buscar PDFs no diretório
    pdf_files = list(Path('.').glob('*.pdf'))

    if not pdf_files:
        print("❌ Nenhum arquivo PDF encontrado")
        return

    print(f"\n📂 {len(pdf_files)} arquivo(s) encontrado(s)\n")

    # Processar
    resultados = processar_pcmso(pdf_files)

    # Consolidar
    output = consolidar_excel(resultados)
    print(f"\n✓ Arquivos gerados: {output} e CSVs correspondentes")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
