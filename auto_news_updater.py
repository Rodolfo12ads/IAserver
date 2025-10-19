import time
import requests
import logging
from datetime import datetime
import threading

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════════

INTERVALO_MINUTOS = 10  # A cada 10 minutos
URL_SERVIDOR = "http://127.0.0.1:5000"  # URL do seu servidor GoldAI
ENDPOINT_UPDATE = f"{URL_SERVIDOR}/force-update"
ENDPOINT_STATUS = f"{URL_SERVIDOR}/status"
ENDPOINT_HEALTH = f"{URL_SERVIDOR}/health"
TIMEOUT = 30  # segundos

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE LOGGING
# ═══════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('auto_news_updater.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# FUNÇÕES
# ═══════════════════════════════════════════════════════════════════════

def verificar_servidor():
    """Verifica se o servidor está online"""
    try:
        response = requests.get(ENDPOINT_HEALTH, timeout=TIMEOUT)
        if response.status_code == 200:
            logger.info("✅ Servidor está online")
            return True
        else:
            logger.error(f"❌ Servidor respondeu com status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Não consegui conectar ao servidor em {URL_SERVIDOR}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar servidor: {e}")
        return False

def obter_status_servidor():
    """Obtém status detalhado do servidor"""
    try:
        response = requests.get(ENDPOINT_STATUS, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            logger.info("📊 Status do Servidor:")
            logger.info(f"   - Total de sinais: {data['statistics']['total_signals']}")
            logger.info(f"   - Chamadas API hoje: {data['statistics']['api_calls_today']}/{data['statistics']['api_remaining']} restantes")
            logger.info(f"   - Eventos em cache: {data['cache']['economic_events']}")
            logger.info(f"   - Notícias em cache: {data['cache']['news_cached']}")
            logger.info(f"   - Sentimento: {data['market_sentiment']}")
            
            if data['next_event']:
                logger.info(f"   - Próximo evento: {data['next_event']['name']} em {data['next_event']['minutes_away']} min")
            
            return data
        else:
            logger.warning(f"⚠️ Erro ao obter status: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro ao obter status: {e}")
        return None

def forcar_atualizacao():
    """Força atualização de calendário e notícias"""
    try:
        logger.info("📥 Forçando atualização...")
        response = requests.post(ENDPOINT_UPDATE, timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Atualização iniciada:")
            logger.info(f"   - Calendário: {data['calendar']}")
            logger.info(f"   - Notícias: {data['news']}")
            return True
        else:
            logger.error(f"❌ Erro na atualização: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Não consegui conectar ao servidor")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao forçar atualização: {e}")
        return False

def loop_atualizacao():
    """Loop principal de atualização"""
    logger.info("🔄 Auto News Updater iniciado")
    logger.info(f"⏱️  Intervalo de atualização: {INTERVALO_MINUTOS} minutos")
    logger.info(f"🌐 Servidor: {URL_SERVIDOR}\n")
    
    contador = 0
    
    while True:
        try:
            contador += 1
            logger.info(f"═══════════════════════════════════════════════════════════════")
            logger.info(f"📍 Ciclo #{contador} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            
            # Verificar se servidor está online
            if not verificar_servidor():
                logger.warning("⚠️ Servidor offline. Aguardando próxima tentativa...")
                time.sleep(INTERVALO_MINUTOS * 60)
                continue
            
            # Obter status do servidor
            obter_status_servidor()
            
            # Forçar atualização
            forcar_atualizacao()
            
            logger.info(f"⏳ Próxima atualização em {INTERVALO_MINUTOS} minutos")
            logger.info(f"═══════════════════════════════════════════════════════════════\n")
            
            # Aguardar
            time.sleep(INTERVALO_MINUTOS * 60)
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Atualizador de notícias interrompido pelo usuário.")
            break
        except Exception as e:
            logger.error(f"❌ Erro no loop: {e}")
            logger.info(f"⏳ Tentando novamente em {INTERVALO_MINUTOS} minutos")
            time.sleep(INTERVALO_MINUTOS * 60)

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    try:
        loop_atualizacao()
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        import traceback
        logger.error(traceback.format_exc())