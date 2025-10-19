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
        self.csv_path = CSV_PATH
        
        # Cache
        self.economic_events = []
        self.news_cache = deque(maxlen=100)
        self.price_cache = deque(maxlen=500)
        self.signal_cache = {}
        
        # Timestamps
        self.last_news_fetch = None
        self.last_calendar_fetch = None
        self.last_price_fetch = None
        self.csv_last_modified = None
        
        # Estatísticas
        self.total_signals = 0
        self.accurate_signals = 0
        self.api_calls_today = 0
        self.api_reset_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        
        # Performance tracking
        self.signal_history = deque(maxlen=200)
        self.prediction_accuracy = {}
        
        logger.info("[OK] Servidor GoldAI Pro v2.0 inicializado")
        self.verify_csv_exists()
        self.start_background_updates()
    
    def verify_csv_exists(self):
        """Verifica se o arquivo CSV existe"""
        if os.path.exists(self.csv_path):
            logger.info(f"[OK] Arquivo CSV encontrado: {self.csv_path}")
        else:
            logger.warning(f"[WARN] Arquivo CSV não encontrado: {self.csv_path}")
    
    def load_csv_calendar(self):
        """Carrega eventos do arquivo CSV"""
        try:
            if not os.path.exists(self.csv_path):
                logger.warning(f"[WARN] Arquivo CSV não existe: {self.csv_path}")
                return False
            
            csv_events = []
            file_mod_time = os.path.getmtime(self.csv_path)
            
            # Verificar se o arquivo foi modificado desde a última leitura
            if self.csv_last_modified and file_mod_time == self.csv_last_modified:
                logger.debug("[CACHE] CSV não foi modificado, usando cache")
                return True
            
            logger.info(f"[DEBUG] Abrindo CSV: {self.csv_path}")
            
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Debug: mostrar colunas encontradas
                if reader.fieldnames:
                    logger.info(f"[DEBUG] Colunas encontradas: {reader.fieldnames}")
                
                row_count = 0
                for row in reader:
                    row_count += 1
                    
                    # Pular linhas vazias
                    if not any(row.values()):
                        logger.debug(f"[DEBUG] Linha {row_count} vazia, pulando")
                        continue
                    
                    try:
                        # Extrair evento (Evento em português)
                        event_name = row.get('Evento', '').strip()
                        if not event_name:
                            event_name = row.get('Event', '').strip()
                        
                        if not event_name or event_name.isspace():
                            logger.debug(f"[DEBUG] Linha {row_count}: evento vazio")
                            continue
                        
                        # Extrair data (Data em português)
                        event_date = row.get('Data', '').strip()
                        if not event_date:
                            event_date = row.get('Date', '').strip()
                        
                        if not event_date or event_date.isspace():
                            logger.debug(f"[DEBUG] Linha {row_count}: data vazia - {event_name}")
                            continue
                        
                        # Extrair impacto (Impacto em português)
                        impact = row.get('Impacto', 'MEDIUM').strip()
                        if not impact:
                            impact = row.get('Impact', 'MEDIUM').strip()
                        
                        impact = impact.upper()
                        if impact not in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                            impact = 'MEDIUM'
                        
                        # Extrair moeda (Moeda em português)
                        currency = row.get('Moeda', 'USD').strip()
                        if not currency:
                            currency = row.get('Currency', 'USD').strip()
                        currency = currency.upper()
                        
                        # Parsear data ISO 8601 com timezone
                        event_datetime = None
                        
                        # Formato: 2025-10-14T12:20:00-04:00
                        if 'T' in event_date:
                            try:
                                # Remover timezone (+HH:MM ou -HH:MM) para parsear
                                date_part = event_date.split('+')[0].split('-04:00')[0].split('-05:00')[0]
                                event_datetime = datetime.fromisoformat(date_part)
                            except:
                                try:
                                    # Tentar com fromisoformat direto (Python 3.7+)
                                    event_datetime = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                except:
                                    pass
                        
                        # Se não conseguiu parsear como ISO, tentar formatos alternativos
                        if event_datetime is None:
                            formatos = [
                                "%Y-%m-%d %H:%M",
                                "%d/%m/%Y %H:%M",
                                "%Y-%m-%d",
                                "%d/%m/%Y",
                            ]
                            
                            for fmt in formatos:
                                try:
                                    event_datetime = datetime.strptime(event_date, fmt)
                                    break
                                except:
                                    continue
                        
                        if event_datetime is None:
                            logger.warning(f"[WARN] Não consegui parsear data: '{event_date}' ({event_name})")
                            continue
                        
                        csv_events.append({
                            'name': event_name,
                            'time': event_datetime,
                            'impact': impact,
                            'currency': currency,
                            'source': 'CSV'
                        })
                        
                        logger.debug(f"[DEBUG] Evento carregado: {event_name} - {event_datetime} ({impact})")
                        
                    except Exception as e:
                        logger.warning(f"[WARN] Erro ao processar linha {row_count}: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                        continue
                
                logger.info(f"[DEBUG] Total de linhas lidas: {row_count}")
            
            # Atualizar eventos
            self.economic_events = csv_events
            self.economic_events.sort(key=lambda x: x['time'])
            self.csv_last_modified = file_mod_time
            
            logger.info(f"[OK] Calendário carregado do CSV: {len(csv_events)} eventos validos")
            
            if csv_events:
                for event in csv_events[:5]:
                    logger.info(f"     - {event['name']} ({event['time'].strftime('%d/%m %H:%M')}) - {event['impact']}")
            
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Carregando CSV: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
                    
                    # Carregar eventos do CSV
                    self.load_csv_calendar()
                    
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
    
    def check_news_impact(self, minutes_before=20, minutes_after=30):
        """Verifica eventos próximos"""
        try:
            now = datetime.now()
            critical_events = []
            
            for event in self.economic_events:
                time_diff = (event['time'] - now).total_seconds() / 60
                
                if -minutes_after <= time_diff <= minutes_before:
                    critical_events.append({
                        'event_name': event['name'],
                        'impact': event['impact'],
                        'minutes_away': int(time_diff),
                        'currency': event['currency'],
                        'source': event.get('source', 'Unknown')
                    })
            
            if critical_events:
                critical_events.sort(key=lambda x: (
                    {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}.get(x['impact'], 4),
                    abs(x['minutes_away'])
                ))
                
                return {
                    'has_event': True,
                    **critical_events[0],
                    'total_events': len(critical_events)
                }
            
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
                
                logger.warning(f"[EVENT] {news_impact['event_name']} em {news_impact['minutes_away']}min")
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
                'uptime': str(datetime.now() - self.last_calendar_fetch) if self.last_calendar_fetch else 'N/A',
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
                    'calendar': self.last_calendar_fetch.strftime('%H:%M:%S') if self.last_calendar_fetch else 'Never',
                    'news': self.last_news_fetch.strftime('%H:%M:%S') if self.last_news_fetch else 'Never'
                },
                'csv_info': {
                    'path': self.csv_path,
                    'exists': os.path.exists(self.csv_path),
                    'last_modified': datetime.fromtimestamp(os.path.getmtime(self.csv_path)).strftime('%d/%m %H:%M:%S') if os.path.exists(self.csv_path) else None
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
        'last_update': gold_server.last_calendar_fetch.strftime('%H:%M:%S') if gold_server.last_calendar_fetch else None
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
            'GET /calendar': 'Calendario economico (CSV + API)',
            'GET /news': 'Noticias recentes',
            'GET /status': 'Status do sistema',
            'GET /history': 'Historico de sinais',
            'GET /health': 'Health check'
        }
    }), 200

@app.route('/force-update', methods=['POST'])
@error_handler
def force_update():
    threading.Thread(target=gold_server.load_csv_calendar).start()
    if gold_server.api_calls_today < API_RATE_LIMIT - 10:
        threading.Thread(target=gold_server.fetch_gold_news).start()
        news_status = 'updating'
    else:
        news_status = 'skipped (API limit)'
    return jsonify({
        'message': 'Atualizacao iniciada',
        'calendar': 'updating (CSV)',
        'news': news_status
    }), 200

# Inicialização
if __name__ == '__main__':
    print("="*70)
    print(" "*10 + "GOLDAI PRO SERVER v2.0 - COM SUPORTE A CSV")
    print("="*70)
    print("\n[OK] Recursos implementados:")
    print("  - Carregamento de calendário do CSV")
    print("  - Sistema de cache inteligente")
    print("  - Controle automatico de rate limit")
    print("  - Logging estruturado (UTF-8)")
    print("  - Analise de sentimento ponderada")
    print("  - Calendario economico em tempo real")
    print("\n[INFO] Configurações:")
    print(f"  - Arquivo CSV: {CSV_PATH}")
    print(f"  - Alpha Vantage (Limite: {API_RATE_LIMIT}/dia)")
    print("\n[INFO] Endpoints disponiveis:")
    print("  POST /signal       -> Gerar sinal de trading")
    print("  GET  /calendar     -> Proximos eventos (CSV)")
    print("  GET  /news         -> Noticias recentes")
    print("  GET  /status       -> Status do sistema")
    print("  GET  /history      -> Historico de sinais")
    print("  POST /force-update -> Forcar atualizacao")
    print("  GET  /health       -> Health check")
    print("\n" + "="*70)
    print("[START] Servidor iniciando em: http://127.0.0.1:5000")
    print("[LOG] Logs salvos em: goldai_server.log")
    print("="*70 + "\n")
    
    try:
        file_handler = logging.FileHandler('goldai_server.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[WARN] Nao foi possivel criar arquivo de log: {e}")
    
    # Carregar calendário do CSV na inicialização
    logger.info("[START] Iniciando carregamento do CSV...")
    gold_server.load_csv_calendar()
    
    # Atualizar dados da API
    logger.info("[START] Iniciando atualizacao de noticias...")
    gold_server.fetch_gold_news()
    logger.info("[OK] Sistema pronto!")
    
    # Iniciar servidor

    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
