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
        """Extrai cargos com detecção de padrões"""
        text = self.full_text

        match = re.search(
            r'QUADRO\s+DE\s+CARGOS(.*?)(?:02\s*[-–]\s*APRESENTAÇÃO|HISTÓRICO|Ambiente|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            cargo_text = match.group(1)

            # DEBUG: Visualizar texto da seção de cargos
            print("\n" + "="*50)
            print("DEBUG: Texto extraído para CARGOS:")
            print(cargo_text[:2000])
            print("="*50 + "\n")

            lines = cargo_text.split('\n')
            current_setor = ""

            for line in lines:
                line = line.strip()

                # Detecção de setor mais flexível (Aceita EST, SETOR, LOCAL, GHE)
                if (('EST' in line and '-' in line) or 
                    line.upper().startswith(('SETOR', 'LOCAL', 'DEPARTAMENTO', 'GHE'))):
                    current_setor = line

                elif line and current_setor:
                    # Tenta capturar: "NOME DO CARGO" seguido de "QUANTIDADE" (com ou sem parênteses)
                    # Ex: "MOTORISTA 1", "MOTORISTA (01)", "MOTORISTA - 1"
                    match_cargo = re.search(r'^(.+?)[\s\-_]+(?:\(?(\d+)\)?)$', line)
                    
                    if match_cargo:
                        try:
                            cargo_nome = match_cargo.group(1).strip().upper()
                            quantidade = int(match_cargo.group(2))

                            # Filtros para evitar falsos positivos (cabeçalhos de tabela, etc)
                            if (len(cargo_nome) > 3 and 
                                'EST' not in cargo_nome and 
                                'SETOR' not in cargo_nome and
                                'QUADRO' not in cargo_nome):

                                self.cargos.append({
                                    'setor': current_setor.strip(),
                                    'cargo': cargo_nome,
                                    'quantidade': str(quantidade)
                                })
                        except ValueError:
                            pass

        # Remover duplicatas
        seen = set()
        unique = []
        for cargo in self.cargos:
            key = (cargo['setor'], cargo['cargo'])
            if key not in seen:
                seen.add(key)
                unique.append(cargo)

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
                'cargo': cargo.get('cargo'),
                'quantidade': cargo.get('quantidade')
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
    print(f"\n✓ Excel gerado: {output}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
