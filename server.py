from flask import Flask, jsonify, request
import requests
from datetime import datetime, timedelta
import threading
import time
import json
from collections import deque
import logging
from functools import wraps
import sys
import os
import csv

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE ENCODING (WINDOWS)
# ═══════════════════════════════════════════════════════════════════════

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════
ALPHA_VANTAGE_KEY = "1SNBE21SNHMIW6LP"
API_RATE_LIMIT = 500
CACHE_DURATION_MINUTES = 15
NEWS_CSV_URL = "https://drive.google.com/uc?export=download&id=1TIHUF9zKnUVA5AZFHJHOTmytdQd3_YZ6"

# ═══════════════════════════════════════════════════════════════════════
# DECORADORES
# ═══════════════════════════════════════════════════════════════════════

def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Erro em {func.__name__}: {str(e)}")
            return jsonify({
                'error': str(e),
                'function': func.__name__
            }), 500
    return wrapper

# ═══════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

class GoldTradingServer:
    def __init__(self):
        self.alpha_key = ALPHA_VANTAGE_KEY
        self.csv_url = NEWS_CSV_URL
        
        # Cache
        self.economic_events = []
        self.news_cache = deque(maxlen=100)
        self.price_cache = deque(maxlen=500)
        self.signal_cache = {}
        
        # Timestamps
        self.last_news_fetch = None
        self.last_calendar_fetch = None
        self.last_price_fetch = None
        self.last_csv_fetch = None
        
        # Estatísticas
        self.total_signals = 0
        self.accurate_signals = 0
        self.api_calls_today = 0
        self.api_reset_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        
        # Performance tracking
        self.signal_history = deque(maxlen=200)
        self.prediction_accuracy = {}
        
        logger.info("[OK] Servidor GoldAI Pro v2.0 inicializado")
        self.start_background_updates()
    
    def generate_future_events(self):
        """Gera eventos futuros para teste se o CSV estiver vazio"""
        try:
            now = datetime.now()
            future_events = []
            
            # Eventos de exemplo para os próximos dias
            sample_events = [
                {"name": "Decisão da taxa de juros do FED", "hours_ahead": 2, "impact": "ALTA"},
                {"name": "Folha de Pagamento Não Agrícola", "hours_ahead": 24, "impact": "ALTA"},
                {"name": "Dados de inflação do IPC", "hours_ahead": 6, "impact": "ALTA"},
                {"name": "Vendas no varejo", "hours_ahead": 12, "impact": "MÉDIA"},
                {"name": "Pedidos Iniciais de Seguro-Desemprego", "hours_ahead": 18, "impact": "MÉDIO"},
            ]
            
            for event in sample_events:
                event_time = now + timedelta(hours=event["hours_ahead"])
                future_events.append({
                    'name': event["name"],
                    'time': event_time,
                    'impact': event["impact"],
                    'currency': 'USD',
                    'source': 'Gerado'
                })
            
            return future_events
            
        except Exception as e:
            logger.error(f"[ERROR] Gerando eventos futuros: {e}")
            return []
    
    def ensure_calendar_data(self):
        """Garante que sempre tenha dados de calendário FUTUROS"""
        try:
            # Remove eventos passados primeiro
            now = datetime.now()
            self.economic_events = [e for e in self.economic_events if e['time'] > now]
            
            if not self.economic_events:
                logger.info("[INFO] Sem eventos futuros, buscando da API externa...")
                external_events = self.fetch_external_calendar()
                if external_events:
                    self.economic_events = [e for e in external_events if e['time'] > now]
                    self.economic_events.sort(key=lambda x: x['time'])
                    self.last_csv_fetch = datetime.now()
                    logger.info(f"[OK] {len(self.economic_events)} eventos futuros carregados")
                
                # Se ainda estiver vazio, gera eventos de teste
                if not self.economic_events:
                    logger.info("[INFO] Gerando eventos futuros para teste...")
                    future_events = self.generate_future_events()
                    self.economic_events = future_events
                    logger.info(f"[OK] {len(future_events)} eventos de teste gerados")
                    
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Garantindo dados de calendário: {e}")
            return False
    
    def load_csv_from_drive(self):
        """Carrega eventos do CSV do Google Drive sem pandas"""
        try:
            logger.info(f"[API] Buscando CSV do Google Drive: {self.csv_url}")
            
            # Fazer download do CSV
            response = requests.get(self.csv_url, timeout=30)
            response.raise_for_status()
            
            # Decodificar o conteúdo
            content = response.content.decode('utf-8')
            lines = content.split('\n')
            
            csv_events = []
            reader = csv.DictReader(lines)
            
            # Debug: mostrar colunas encontradas
            if reader.fieldnames:
                logger.info(f"[DEBUG] Colunas encontradas: {reader.fieldnames}")
            
            row_count = 0
            for row in reader:
                row_count += 1
                
                # Pular linhas vazias
                if not any(row.values()):
                    continue
                
                try:
                    # Extrair evento
                    event_name = row.get('Evento', '').strip()
                    if not event_name:
                        event_name = row.get('Event', '').strip()
                    
                    if not event_name:
                        continue
                    
                    # Extrair data
                    event_date = row.get('Data', '').strip()
                    if not event_date:
                        event_date = row.get('Date', '').strip()
                    
                    if not event_date:
                        continue
                    
                    # Extrair hora
                    event_time_str = row.get('Hora', '').strip()
                    if not event_time_str:
                        event_time_str = row.get('Time', '09:30').strip()
                    
                    # Extrair impacto
                    impact = row.get('Impacto', 'MEDIUM').strip()
                    if not impact:
                        impact = row.get('Impact', 'MEDIUM').strip()
                    
                    impact = impact.upper()
                    if impact not in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'ALTA', 'MÉDIA', 'MÉDIO', 'BAIXA']:
                        impact = 'MEDIUM'
                    
                    # Extrair moeda
                    currency = row.get('Moeda', 'USD').strip()
                    if not currency:
                        currency = row.get('Currency', 'USD').strip()
                    currency = currency.upper()
                    
                    # Combinar data e hora
                    datetime_str = f"{event_date} {event_time_str}"
                    
                    # Parsear data
                    event_datetime = None
                    
                    # Tentar formatos de data/hora
                    formatos = [
                        "%Y-%m-%d %H:%M",
                        "%d/%m/%Y %H:%M", 
                        "%Y-%m-%d",
                        "%d/%m/%Y",
                    ]
                    
                    for fmt in formatos:
                        try:
                            event_datetime = datetime.strptime(datetime_str, fmt)
                            break
                        except:
                            continue
                    
                    if event_datetime is None:
                        logger.warning(f"[WARN] Não consegui parsear data: '{datetime_str}' ({event_name})")
                        continue
                    
                    # Só adiciona eventos FUTUROS
                    if event_datetime > datetime.now():
                        csv_events.append({
                            'name': event_name,
                            'time': event_datetime,
                            'impact': impact,
                            'currency': currency,
                            'source': 'Google Drive CSV'
                        })
                        logger.debug(f"[DEBUG] Evento futuro carregado: {event_name} - {event_datetime} ({impact})")
                    
                except Exception as e:
                    logger.warning(f"[WARN] Erro ao processar linha {row_count}: {e}")
                    continue
            
            logger.info(f"[DEBUG] Total de linhas processadas: {row_count}")
            logger.info(f"[DEBUG] Eventos futuros encontrados: {len(csv_events)}")
            
            # Atualizar eventos
            if csv_events:
                self.economic_events.extend(csv_events)
                self.economic_events.sort(key=lambda x: x['time'])
                self.last_csv_fetch = datetime.now()
            
            logger.info(f"[OK] Calendário carregado do Google Drive: {len(csv_events)} eventos futuros")
            
            if csv_events:
                for event in csv_events[:5]:
                    logger.info(f"     - {event['name']} ({event['time'].strftime('%d/%m %H:%M')}) - {event['impact']}")
            
            return len(csv_events) > 0
            
        except Exception as e:
            logger.error(f"[ERROR] Carregando CSV do Google Drive: {e}")
            return False
    
    def fetch_external_calendar(self):
        """Busca calendário de fonte pública (fallback)"""
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            logger.info(f"[API] Buscando calendário externo de {url}")
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            events = data if isinstance(data, list) else data.get("events", [])
            logger.info(f"[API] {len(events)} eventos recebidos")
            
            external_events = []
            count_usd = 0
            
            for ev in events:
                country = ev.get("country", "")
                currency = ev.get("currency", "")
                
                if "US" not in country.upper() and currency.upper() != "USD":
                    continue
                
                impact = ev.get("impact", "Medium").capitalize()
                
                if impact not in ["Medium", "High"]:
                    continue
                
                # Parsear data do evento externo
                date_str = ev.get("date", "")
                time_str = ev.get("time", "")
                
                try:
                    if 'T' in date_str:
                        event_datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        datetime_str = f"{date_str} {time_str}" if time_str else date_str
                        event_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                    
                    # Só adiciona eventos FUTUROS
                    if event_datetime > datetime.now():
                        external_events.append({
                            'name': ev.get("title", "Evento"),
                            'time': event_datetime,
                            'impact': impact.upper(),
                            'currency': 'USD',
                            'source': 'External API'
                        })
                        count_usd += 1
                    
                except Exception as e:
                    continue
            
            logger.info(f"[OK] {count_usd} eventos USD futuros carregados da API externa")
            return external_events
            
        except Exception as e:
            logger.error(f"[ERROR] Falha ao buscar calendário externo: {e}")
            return []
    
    def load_calendar_events(self):
        """Carrega eventos do Google Drive com fallback para API externa"""
        try:
            # Primeiro tenta carregar do Google Drive
            drive_success = self.load_csv_from_drive()
            
            if not drive_success or not self.economic_events:
                # Fallback para API externa
                logger.info("[INFO] Fallback para API externa...")
                external_events = self.fetch_external_calendar()
                if external_events:
                    self.economic_events.extend(external_events)
                    self.economic_events.sort(key=lambda x: x['time'])
                    self.last_csv_fetch = datetime.now()
                    logger.info(f"[OK] {len(external_events)} eventos futuros carregados da API externa")
            
            # Garante que sempre tenha dados
            self.ensure_calendar_data()
            
            return len(self.economic_events) > 0
            
        except Exception as e:
            logger.error(f"[ERROR] Carregando eventos: {e}")
            return False
    
    def start_background_updates(self):
        """Inicia threads de atualização em background"""
        def update_loop():
            while True:
                try:
                    # Resetar contador de API diariamente
                    if datetime.now() >= self.api_reset_time:
                        self.api_calls_today = 0
                        self.api_reset_time += timedelta(days=1)
                        logger.info("[RESET] Contador de API resetado")
                    
                    # Garante dados de calendário primeiro
                    self.ensure_calendar_data()
                    
                    # Carregar eventos do calendário
                    self.load_calendar_events()
                    
                    # Atualizar dados da API (se disponível)
                    if self.api_calls_today < API_RATE_LIMIT - 50:
                        self.fetch_gold_news()
                    else:
                        logger.warning("[WARN] Limite de API próximo, pulando atualização")
                    
                    # Limpar cache antigo
                    self.clean_old_cache()
                    
                    time.sleep(900)  # 15 minutos
                    
                except Exception as e:
                    logger.error(f"[ERROR] Background: {e}")
                    time.sleep(300)
        
        threading.Thread(target=update_loop, daemon=True).start()
        logger.info("[OK] Thread de atualização iniciada")
    
    def clean_old_cache(self):
        """Remove dados antigos do cache"""
        try:
            now = datetime.now()
            
            # Remover eventos passados
            self.economic_events = [
                e for e in self.economic_events 
                if e['time'] > now
            ]
            
            # Limpar sinais antigos (> 1 hora)
            old_signals = [
                k for k, v in self.signal_cache.items()
                if (now - v['timestamp']).total_seconds() > 3600
            ]
            for k in old_signals:
                del self.signal_cache[k]
                
        except Exception as e:
            logger.error(f"[ERROR] Limpando cache: {e}")
    
    def fetch_gold_news(self):
        """Busca notícias sobre ouro"""
        try:
            if self.api_calls_today >= API_RATE_LIMIT:
                logger.warning("[WARN] Limite diário de API atingido")
                return
            
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'topics': 'economy_fiscal,economy_monetary,financial_markets',
                'tickers': 'FOREX:USD',
                'apikey': self.alpha_key,
                'limit': 50
            }
            
            response = requests.get(url, params=params, timeout=15)
            self.api_calls_today += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if 'feed' not in data:
                    logger.warning(f"[WARN] Resposta inesperada da API")
                    return
                
                feed = data.get('feed', [])
                new_items = 0
                
                for item in feed[:30]:
                    try:
                        sentiment_score = float(item.get('overall_sentiment_score', 0))
                        
                        if sentiment_score > 0.15:
                            sentiment = 'BULLISH'
                        elif sentiment_score < -0.15:
                            sentiment = 'BEARISH'
                        else:
                            sentiment = 'NEUTRAL'
                        
                        news_item = {
                            'title': item.get('title', '')[:120],
                            'source': item.get('source', 'Unknown'),
                            'sentiment': sentiment,
                            'score': round(sentiment_score, 3),
                            'time': item.get('time_published', '')[:10],
                            'relevance': round(float(item.get('relevance_score', 0.5)), 2),
                            'url': item.get('url', '')
                        }
                        
                        if news_item not in self.news_cache:
                            self.news_cache.append(news_item)
                            new_items += 1
                            
                    except Exception as e:
                        continue
                
                self.last_news_fetch = datetime.now()
                logger.info(f"[OK] Notícias: +{new_items} novos (total: {len(self.news_cache)})")
            else:
                logger.warning(f"[WARN] API status {response.status_code}")
                
        except Exception as e:
            logger.error(f"[ERROR] Notícias: {e}")
    
    def check_news_impact(self, minutes_before=180, minutes_after=120):
        """Verifica eventos próximos - JANELA AUMENTADA"""
        try:
            now = datetime.now()
            critical_events = []
            
            logger.info(f"[DEBUG] Verificando {len(self.economic_events)} eventos...")
            logger.info(f"[DEBUG] Janela aumentada: -{minutes_after}min a +{minutes_before}min")
            
            for event in self.economic_events:
                time_diff = (event['time'] - now).total_seconds() / 60
                
                # Janela dinâmica baseada no impacto
                if event['impact'] in ['ALTA', 'HIGH', 'CRITICAL']:
                    event_minutes_before = 180  # 3 horas para eventos ALTOS
                    event_minutes_after = 120   # 2 horas após
                else:
                    event_minutes_before = 60   # 1 hora para eventos médios
                    event_minutes_after = 60    # 1 hora após
                
                logger.info(f"[DEBUG] Evento: {event['name']} - Tempo: {time_diff:.1f}min - Impacto: {event['impact']} - Janela: -{event_minutes_after}/+{event_minutes_before}min")
                
                # Verifica se o evento está na janela de bloqueio
                if -event_minutes_after <= time_diff <= event_minutes_before:
                    logger.info(f"[DEBUG] ⚠️ EVENTO NA JANELA: {event['name']} em {time_diff:.1f}min")
                    critical_events.append({
                        'event_name': event['name'],
                        'impact': event['impact'],
                        'minutes_away': int(time_diff),
                        'currency': event['currency'],
                        'source': event.get('source', 'Unknown')
                    })
            
            if critical_events:
                logger.info(f"[DEBUG] 🚨 {len(critical_events)} eventos críticos encontrados")
                # Ordena por impacto e proximidade
                critical_events.sort(key=lambda x: (
                    {'CRITICAL': 0, 'HIGH': 1, 'ALTA': 1, 'MEDIUM': 2, 'MÉDIA': 2, 'MÉDIO': 2, 'LOW': 3, 'BAIXA': 3}.get(x['impact'], 4),
                    abs(x['minutes_away'])
                ))
                
                result = {
                    'has_event': True,
                    **critical_events[0],
                    'total_events': len(critical_events)
                }
                logger.info(f"[DEBUG] 🔒 BLOQUEANDO: {result['event_name']} em {result['minutes_away']}min")
                return result
            else:
                logger.info("[DEBUG] ✅ Nenhum evento crítico - TRADE LIBERADO")
            
            return {'has_event': False}
            
        except Exception as e:
            logger.error(f"[ERROR] Verificando eventos: {e}")
            return {'has_event': False}
    
    def generate_trading_signal(self, technical_data):
        """Gera sinal de trading"""
        try:
            action = technical_data.get('action', 'NONE')
            confidence = technical_data.get('confidence', 0)
            ema5 = technical_data.get('ema5', 0)
            ema15 = technical_data.get('ema15', 0)
            ema50 = technical_data.get('ema50', 0)
            adx = technical_data.get('adx', 0)
            rsi = technical_data.get('rsi', 50)
            current_price = technical_data.get('current_price', 0)
            
            signal_hash = f"{action}_{int(confidence)}_{int(adx)}_{int(rsi)}"
            
            if signal_hash in self.signal_cache:
                cached = self.signal_cache[signal_hash]
                if (datetime.now() - cached['timestamp']).total_seconds() < 120:
                    logger.debug("[CACHE] Retornando sinal do cache")
                    return cached['signal']
            
            # CORREÇÃO: Verifica eventos primeiro (agora com janela maior)
            news_impact = self.check_news_impact()
            
            if news_impact['has_event']:
                result = {
                    'signal': 'HOLD',
                    'action': 'WAIT',
                    'confidence': 0,
                    'reason': f"Evento próximo: {news_impact['event_name']}",
                    'event_warning': True,
                    'event_name': news_impact['event_name'],
                    'minutes_to_event': news_impact['minutes_away'],
                    'impact_level': news_impact['impact'],
                    'event_source': news_impact.get('source', 'Unknown'),
                    'total_events': news_impact.get('total_events', 1)
                }
                
                logger.warning(f"[EVENT] {news_impact['event_name']} em {news_impact['minutes_away']}min - BLOQUEANDO TRADES")
                return result
            
            news_sentiment = self._analyze_news_sentiment()
            technical_strength = self._calculate_technical_strength(technical_data)
            final_signal = self._combine_signals(
                action, confidence, news_sentiment, 
                technical_strength, technical_data
            )
            
            self.signal_cache[signal_hash] = {
                'signal': final_signal,
                'timestamp': datetime.now()
            }
            
            self.total_signals += 1
            self.signal_history.append({
                'action': final_signal['action'],
                'confidence': final_signal['confidence'],
                'timestamp': datetime.now().isoformat(),
                'price': current_price
            })
            
            logger.info(f"[SIGNAL] {final_signal['action']} (Conf: {final_signal['confidence']:.1f}%)")
            
            return final_signal
            
        except Exception as e:
            logger.error(f"[ERROR] Gerando sinal: {e}")
            return {
                'signal': 'ERROR',
                'action': 'HOLD',
                'confidence': 0,
                'reason': f'Erro: {str(e)}'
            }
    
    def _analyze_news_sentiment(self):
        """Analisa sentimento"""
        try:
            if not self.news_cache:
                return 'NEUTRAL'
            
            recent_news = [
                news for news in self.news_cache
                if news.get('relevance', 0) > 0.3
            ][:15]
            
            if not recent_news:
                return 'NEUTRAL'
            
            bullish_score = 0
            bearish_score = 0
            
            for news in recent_news:
                relevance = news.get('relevance', 0.5)
                sentiment = news.get('sentiment', 'NEUTRAL')
                
                if sentiment == 'BULLISH':
                    bullish_score += relevance
                elif sentiment == 'BEARISH':
                    bearish_score += relevance
            
            diff = abs(bullish_score - bearish_score)
            
            if diff < 0.3:
                return 'NEUTRAL'
            elif bullish_score > bearish_score:
                return 'BULLISH'
            else:
                return 'BEARISH'
                
        except Exception as e:
            logger.error(f"[ERROR] Sentimento: {e}")
            return 'NEUTRAL'
    
    def _calculate_technical_strength(self, tech_data):
        """Calcula força técnica"""
        try:
            score = 0
            
            adx = tech_data.get('adx', 0)
            if adx >= 40:
                score += 20
            elif adx >= 30:
                score += 15
            elif adx >= 25:
                score += 10
            
            rsi = tech_data.get('rsi', 50)
            action = tech_data.get('action', 'NONE')
            
            if action == 'BUY':
                if 40 <= rsi <= 60:
                    score += 20
                elif 30 <= rsi < 40:
                    score += 15
                elif rsi > 70:
                    score -= 10
            elif action == 'SELL':
                if 40 <= rsi <= 60:
                    score += 20
                elif 60 < rsi <= 70:
                    score += 15
                elif rsi < 30:
                    score -= 10
            
            ema5 = tech_data.get('ema5', 0)
            ema15 = tech_data.get('ema15', 0)
            ema50 = tech_data.get('ema50', 0)
            
            if action == 'BUY' and ema5 > ema15 > ema50:
                score += 30
            elif action == 'BUY' and ema5 > ema15:
                score += 20
            elif action == 'SELL' and ema5 < ema15 < ema50:
                score += 30
            elif action == 'SELL' and ema5 < ema15:
                score += 20
            
            confidence = tech_data.get('confidence', 0) * 100
            score += min(confidence * 0.3, 30)
            
            return min(score, 100)
            
        except Exception as e:
            logger.error(f"[ERROR] Força técnica: {e}")
            return 0
    
    def _combine_signals(self, action, confidence, news_sentiment, technical_strength, tech_data):
        """Combina sinais"""
        
        if action == 'NONE':
            return {
                'signal': 'NONE',
                'action': 'WAIT',
                'confidence': 0,
                'reason': 'Sem sinal técnico',
                'technical_strength': technical_strength,
                'news_sentiment': news_sentiment
            }
        
        base_confidence = confidence * 100 if confidence <= 1 else confidence
        adjusted_confidence = base_confidence
        
        if action == 'BUY':
            if news_sentiment == 'BULLISH':
                adjusted_confidence += 12
            elif news_sentiment == 'BEARISH':
                adjusted_confidence -= 18
        elif action == 'SELL':
            if news_sentiment == 'BEARISH':
                adjusted_confidence += 12
            elif news_sentiment == 'BULLISH':
                adjusted_confidence -= 18
        
        final_confidence = (adjusted_confidence * 0.6) + (technical_strength * 0.4)
        final_confidence = max(0, min(100, final_confidence))
        
        if final_confidence < 60:
            signal_type = 'WEAK'
            final_action = 'WAIT'
            reason = f'Confiança baixa: {final_confidence:.1f}%'
        elif final_confidence < 75:
            signal_type = 'MODERATE'
            final_action = action
            reason = f'Sinal moderado: {final_confidence:.1f}%'
        else:
            signal_type = 'STRONG'
            final_action = action
            reason = f'Sinal forte: {final_confidence:.1f}%'
        
        return {
            'signal': signal_type,
            'action': final_action,
            'confidence': round(final_confidence, 2),
            'reason': reason,
            'news_sentiment': news_sentiment,
            'technical_strength': round(technical_strength, 2),
            'base_confidence': round(base_confidence, 2),
            'timestamp': datetime.now().isoformat(),
            'components': {
                'technical_score': round(base_confidence, 1),
                'news_adjustment': round(adjusted_confidence - base_confidence, 1),
                'technical_strength': round(technical_strength, 1)
            }
        }
    
    def get_system_stats(self):
        """Estatísticas do sistema"""
        try:
            win_rate = 0
            if self.accurate_signals > 0:
                win_rate = (self.accurate_signals / self.total_signals) * 100
            
            next_event = None
            if self.economic_events:
                next_event = self.economic_events[0]
                minutes_away = (next_event['time'] - datetime.now()).total_seconds() / 60
                next_event = {
                    'name': next_event['name'],
                    'time': next_event['time'].strftime('%d/%m %H:%M'),
                    'impact': next_event['impact'],
                    'currency': next_event['currency'],
                    'source': next_event.get('source', 'Unknown'),
                    'minutes_away': int(minutes_away)
                }
            
            overall_sentiment = self._analyze_news_sentiment()
            
            return {
                'status': 'running',
                'uptime': str(datetime.now() - self.last_csv_fetch) if self.last_csv_fetch else 'N/A',
                'statistics': {
                    'total_signals': self.total_signals,
                    'accurate_signals': self.accurate_signals,
                    'win_rate': round(win_rate, 2),
                    'api_calls_today': self.api_calls_today,
                    'api_remaining': API_RATE_LIMIT - self.api_calls_today
                },
                'cache': {
                    'economic_events': len(self.economic_events),
                    'news_cached': len(self.news_cache),
                    'signals_cached': len(self.signal_cache),
                    'price_points': len(self.price_cache)
                },
                'last_updates': {
                    'calendar': self.last_csv_fetch.strftime('%H:%M:%S') if self.last_csv_fetch else 'Never',
                    'news': self.last_news_fetch.strftime('%H:%M:%S') if self.last_news_fetch else 'Never'
                },
                'csv_info': {
                    'source': 'Google Drive',
                    'url': self.csv_url,
                    'last_fetch': self.last_csv_fetch.strftime('%d/%m %H:%M:%S') if self.last_csv_fetch else None
                },
                'next_event': next_event,
                'market_sentiment': overall_sentiment,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Stats: {e}")
            return {'error': str(e)}


# Inicializar
gold_server = GoldTradingServer()

# Endpoints
@app.route('/signal', methods=['POST'])
@error_handler
def signal():
    data = request.get_json() or {}
    technical_data = {
        'action': data.get('technical_signal', 'NONE'),
        'confidence': data.get('technical_score', 0),
        'ema5': data.get('ema5', 0),
        'ema15': data.get('ema15', 0),
        'ema50': data.get('ema50', 0),
        'adx': data.get('adx', 0),
        'rsi': data.get('rsi', 50),
        'current_price': data.get('current_price', 0)
    }
    return jsonify(gold_server.generate_trading_signal(technical_data)), 200

@app.route('/calendar', methods=['GET'])
@error_handler
def calendar():
    now = datetime.now()
    upcoming = []
    for event in gold_server.economic_events:
        if event['time'] > now:
            minutes_away = int((event['time'] - now).total_seconds() / 60)
            upcoming.append({
                'event': event['name'],
                'time': event['time'].strftime('%Y-%m-%d %H:%M'),
                'impact': event['impact'],
                'currency': event['currency'],
                'source': event.get('source', 'Unknown'),
                'minutes_away': minutes_away
            })
    upcoming.sort(key=lambda x: x['time'])
    return jsonify({
        'total': len(upcoming),
        'events': upcoming[:15],
        'last_update': gold_server.last_csv_fetch.strftime('%H:%M:%S') if gold_server.last_csv_fetch else None
    }), 200

@app.route('/news', methods=['GET'])
@error_handler
def news():
    limit = request.args.get('limit', 20, type=int)
    recent = list(gold_server.news_cache)
    recent.reverse()
    sentiment_summary = {
        'BULLISH': sum(1 for n in recent if n['sentiment'] == 'BULLISH'),
        'BEARISH': sum(1 for n in recent if n['sentiment'] == 'BEARISH'),
        'NEUTRAL': sum(1 for n in recent if n['sentiment'] == 'NEUTRAL')
    }
    return jsonify({
        'total': len(gold_server.news_cache),
        'news': recent[:limit],
        'sentiment_summary': sentiment_summary,
        'overall_sentiment': gold_server._analyze_news_sentiment()
    }), 200

@app.route('/status', methods=['GET'])
@error_handler
def status():
    return jsonify(gold_server.get_system_stats()), 200

@app.route('/history', methods=['GET'])
@error_handler
def history():
    limit = request.args.get('limit', 50, type=int)
    recent = list(gold_server.signal_history)[-limit:]
    recent.reverse()
    return jsonify({'total': len(gold_server.signal_history), 'signals': recent}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'version': '2.0'}), 200

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'GoldAI Pro Trading Server',
        'version': '2.0',
        'status': 'running',
        'endpoints': {
            'POST /signal': 'Gerar sinal de trading',
            'GET /calendar': 'Calendario economico (Google Drive)',
            'GET /news': 'Noticias recentes',
            'GET /status': 'Status do sistema',
            'GET /history': 'Historico de sinais',
            'GET /health': 'Health check'
        }
    }), 200

@app.route('/force-update', methods=['POST'])
@error_handler
def force_update():
    threading.Thread(target=gold_server.load_calendar_events).start()
    if gold_server.api_calls_today < API_RATE_LIMIT - 10:
        threading.Thread(target=gold_server.fetch_gold_news).start()
        news_status = 'updating'
    else:
        news_status = 'skipped (API limit)'
    return jsonify({
        'message': 'Atualizacao iniciada',
        'calendar': 'updating (Google Drive + External API)',
        'news': news_status
    }), 200

# Inicialização
if __name__ == '__main__':
    print("="*70)
    print(" "*10 + "GOLDAI PRO SERVER v2.0 - JANELA DE BLOQUEIO CORRIGIDA")
    print("="*70)
    print("\n[OK] Recursos implementados:")
    print("  - ✅ Janela de bloqueio aumentada: 3h antes + 2h depois (eventos ALTOS)")
    print("  - ✅ Janela de bloqueio: 1h antes + 1h depois (eventos MÉDIOS)") 
    print("  - ✅ Bloqueio de eventos funcionando (português/inglês)")
    print("  - ✅ Carregamento de calendário do Google Drive")
    print("  - ✅ Filtro automático de eventos FUTUROS")
    print("\n[INFO] Configurações:")
    print(f"  - Fonte CSV: Google Drive")
    print(f"  - Alpha Vantage (Limite: {API_RATE_LIMIT}/dia)")
    print("\n[INFO] Endpoints disponiveis:")
    print("  POST /signal       -> Gerar sinal de trading")
    print("  GET  /calendar     -> Proximos eventos")
    print("  GET  /news         -> Noticias recentes")
    print("  GET  /status       -> Status do sistema")
    print("  GET  /history      -> Historico de sinais")
    print("  POST /force-update -> Forcar atualizacao")
    print("  GET  /health       -> Health check")
    print("\n" + "="*70)
    
    try:
        file_handler = logging.FileHandler('goldai_server.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[WARN] Nao foi possivel criar arquivo de log: {e}")
    
    # Carregar calendário na inicialização
    logger.info("[START] Iniciando carregamento do calendário...")
    gold_server.load_calendar_events()
    
    # Atualizar dados da API
    logger.info("[START] Iniciando atualizacao de noticias...")
    gold_server.fetch_gold_news()
    logger.info("[OK] Sistema pronto!")
    
    # Iniciar servidor (CONFIGURAÇÃO RENDER)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
