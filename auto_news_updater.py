import time
import requests
import logging
from datetime import datetime
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════════

INTERVALO_MINUTOS = 10  # Intervalo entre atualizações
URL_SERVIDOR = "https://iaserver.onrender.com"  # URL pública do servidor no Render
ENDPOINT_UPDATE = f"{URL_SERVIDOR}/force-update"
ENDPOINT_STATUS = f"{URL_SERVIDOR}/status"
ENDPOINT_HEALTH = f"{URL_SERVIDOR}/health"
TIMEOUT = 30  # segundos

# Link do Google Drive com o CSV de notícias (download direto)
NEWS_CSV_URL = "https://drive.google.com/uc?export=download&id=1TIHUF9zKnUVA5AZFHJHOTmytdQd3_YZ6"

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
            stats = data.get('statistics', {})
            cache = data.get('cache', {})

            logger.info(f"   - Total de sinais: {stats.get('total_signals', 'N/A')}")
            logger.info(f"   - Chamadas API hoje: {stats.get('api_calls_today', 'N/A')}/{stats.get('api_remaining', 'N/A')}")
            logger.info(f"   - Eventos em cache: {cache.get('economic_events', 'N/A')}")
            logger.info(f"   - Notícias em cache: {cache.get('news_cached', 'N/A')}")
            logger.info(f"   - Sentimento: {data.get('market_sentiment', 'N/A')}")

            next_event = data.get('next_event')
            if next_event:
                logger.info(f"   - Próximo evento: {next_event.get('name')} em {next_event.get('minutes_away')} min")

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
            logger.info(f"✅ Atualização iniciada com sucesso:")
            logger.info(f"   - Calendário: {data.get('calendar', 'N/A')}")
            logger.info(f"   - Notícias: {data.get('news', 'N/A')}")
            return True
        else:
            logger.error(f"❌ Erro na atualização: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ Não consegui conectar ao servidor para atualizar")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao forçar atualização: {e}")
        return False


def verificar_news_calendar():
    """Lê o CSV no Google Drive e verifica se há atualizações"""
    try:
        df = pd.read_csv(NEWS_CSV_URL)
        logger.info(f"📰 CSV carregado do Google Drive com {len(df)} registros.")
        if not df.empty:
            ultima_data = df.iloc[-1].get("date", "N/A")
            logger.info(f"   - Última atualização registrada: {ultima_data}")
        return True
    except Exception as e:
        logger.error(f"⚠️ Erro ao ler CSV do Google Drive: {e}")
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
            logger.info("═══════════════════════════════════════════════════════════════")
            logger.info(f"📍 Ciclo #{contador} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

            # Verificar se servidor está online
            if not verificar_servidor():
                logger.warning("⚠️ Servidor offline. Aguardando próxima tentativa...")
                time.sleep(INTERVALO_MINUTOS * 60)
                continue

            # Obter status e forçar atualização
            obter_status_servidor()
            forcar_atualizacao()

            # Checar CSV do Google Drive
            verificar_news_calendar()

            logger.info(f"⏳ Próxima atualização em {INTERVALO_MINUTOS} minutos")
            logger.info("═══════════════════════════════════════════════════════════════\n")

            # Esperar até o próximo ciclo
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
