#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilidades para processamento de CAPTCHA do SICAR.
"""

import os
import base64
import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO

logger = logging.getLogger('captcha_utils')

def process_captcha_image(captcha_src, output_path=None):
    """
    Processa a imagem do CAPTCHA para melhorar a visualização.
    
    Args:
        captcha_src: URL da imagem do CAPTCHA ou string base64
        output_path: Caminho para salvar a imagem processada
        
    Returns:
        str: Caminho da imagem processada ou None
    """
    try:
        # Extrai dados da imagem de base64
        if captcha_src and captcha_src.startswith('data:image'):
            # Extrai dados de base64
            image_data = captcha_src.split(',')[1]
            image_binary = base64.b64decode(image_data)
            
            # Carrega a imagem
            img = Image.open(BytesIO(image_binary))
            
            # Aplica filtros para melhorar a visibilidade
            img = img.convert('L')  # Converte para escala de cinza
            img = ImageEnhance.Contrast(img).enhance(2.0)  # Aumenta o contraste
            img = ImageEnhance.Sharpness(img).enhance(2.0)  # Aumenta a nitidez
            img = img.filter(ImageFilter.DETAIL)  # Adiciona detalhes
            
            # Salva a imagem processada
            if output_path:
                img.save(output_path)
                logger.info(f"Imagem do CAPTCHA processada e salva em {output_path}")
                return output_path
            else:
                # Salva em memória e retorna como base64
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return f"data:image/png;base64,{img_str}"
        
        return None
    except Exception as e:
        logger.error(f"Erro ao processar imagem do CAPTCHA: {str(e)}")
        return None

def enhanced_captcha_image(captcha_src, output_dir):
    """
    Cria múltiplas versões da imagem do CAPTCHA com diferentes processamentos.
    
    Args:
        captcha_src: URL da imagem do CAPTCHA ou string base64
        output_dir: Diretório para salvar as imagens processadas
        
    Returns:
        dict: Dicionário com os caminhos das imagens processadas
    """
    try:
        # Garante que o diretório existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Verifica se a imagem é base64
        if not captcha_src or not captcha_src.startswith('data:image'):
            logger.warning("Formato de imagem inválido")
            return {}
        
        # Extrai dados de base64
        image_data = captcha_src.split(',')[1]
        image_binary = base64.b64decode(image_data)
        
        # Salva a imagem original
        original_path = os.path.join(output_dir, "captcha_original.png")
        with open(original_path, "wb") as f:
            f.write(image_binary)
        
        # Carrega a imagem
        img = Image.open(BytesIO(image_binary))
        
        results = {"original": original_path}
        
        # Versão em escala de cinza
        gray_path = os.path.join(output_dir, "captcha_gray.png")
        img.convert('L').save(gray_path)
        results["gray"] = gray_path
        
        # Versão com alto contraste
        contrast_path = os.path.join(output_dir, "captcha_contrast.png")
        ImageEnhance.Contrast(img.convert('L')).enhance(2.5).save(contrast_path)
        results["contrast"] = contrast_path
        
        # Versão com filtro de borda
        edge_path = os.path.join(output_dir, "captcha_edge.png")
        img.convert('L').filter(ImageFilter.FIND_EDGES).save(edge_path)
        results["edge"] = edge_path
        
        # Versão com filtro de nitidez
        sharp_path = os.path.join(output_dir, "captcha_sharp.png")
        ImageEnhance.Sharpness(img).enhance(2.0).save(sharp_path)
        results["sharp"] = sharp_path
        
        logger.info(f"Geradas {len(results)} versões da imagem do CAPTCHA")
        return results
    
    except Exception as e:
        logger.error(f"Erro ao gerar versões da imagem do CAPTCHA: {str(e)}")
        return {}
