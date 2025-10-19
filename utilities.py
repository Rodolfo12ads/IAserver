# ═══════════════════════════════════════════════════════════════════════
# GOLDAI PRO - UTILITÁRIOS E FERRAMENTAS
# ═══════════════════════════════════════════════════════════════════════

import requests
import json
from datetime import datetime
import time
import csv
import os

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════

SERVER_URL = "http://127.0.0.1:5000"
LOGS_DIR = "logs"
CSV_EXPORT_DIR = "exports"

# Criar diretórios se não existirem
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CSV_EXPORT_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# 1. MONITOR EM TEMPO REAL
# ═══════════════════════════════════════════════════════════════════════

def real_time_monitor(interval_seconds=10):
    """Monitor em tempo real do servidor"""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║         🔍 GOLDAI PRO - MONITOR EM TEMPO REAL             ║")
    print("╚═══════════════════════════════════════════════════════════════╝\n")
    print("Pressione Ctrl+C para parar\n")
    
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("╔═══════════════════════════════════════════════════════════════╗")
            print("║         🔍 GOLDAI PRO - MONITOR EM TEMPO REAL             ║")
            print("╚═══════════════════════════════════════════════════════════════╝\n")
            
            # Status do sistema
            try:
                response = requests.get(f"{SERVER_URL}/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    print(f"⏰ Atualizado em: {datetime.now().strftime('%H:%M:%S')}\n")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print("📊 STATUS DO SISTEMA")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print(f"Status: ✅ {data['status'].upper()}")
                    
                    stats = data.get('statistics', {})
                    print(f"\n📈 ESTATÍSTICAS:")
                    print(f"   Total Sinais: {stats.get('total_signals', 0)}")
                    print(f"   Sinais Corretos: {stats.get('accurate_signals', 0)}")
                    print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
                    print(f"   API Calls Hoje: {stats.get('api_calls_today', 0)}/{stats.get('api_remaining', 0) + stats.get('api_calls_today', 0)}")
                    
                    cache = data.get('cache', {})
                    print(f"\n💾 CACHE:")
                    print(f"   Eventos: {cache.get('economic_events', 0)}")
                    print(f"   Notícias: {cache.get('news_cached', 0)}")
                    print(f"   Sinais: {cache.get('signals_cached', 0)}")
                    
                    next_event = data.get('next_event')
                    if next_event:
                        print(f"\n📰 PRÓXIMO EVENTO:")
                        print(f"   {next_event['name']}")
                        print(f"   ⏰ {next_event['time']} ({next_event['minutes_away']}min)")
                        print(f"   💥 Impacto: {next_event['impact']}")
                    
                    sentiment = data.get('market_sentiment', 'NEUTRAL')
                    sentiment_emoji = {
                        'BULLISH': '📈',
                        'BEARISH': '📉',
                        'NEUTRAL': '➖'
                    }.get(sentiment, '❓')
                    print(f"\n🎯 SENTIMENTO: {sentiment_emoji} {sentiment}")
                    
                else:
                    print(f"❌ Erro: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Erro ao conectar: {e}")
            
            print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"Próxima atualização em {interval_seconds}s... (Ctrl+C para sair)")
            
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        print("\n\n✅ Monitor finalizado!")


# ═══════════════════════════════════════════════════════════════════════
# 2. EXPORTAR CALENDÁRIO PARA CSV
# ═══════════════════════════════════════════════════════════════════════

def export_calendar_to_csv():
    """Exporta calendário econômico para CSV"""
    print("📊 Exportando calendário econômico...\n")
    
    try:
        response = requests.get(f"{SERVER_URL}/calendar", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            if not events:
                print("⚠️ Nenhum evento encontrado!")
                return
            
            # Nome do arquivo com timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{CSV_EXPORT_DIR}/calendar_{timestamp}.csv"
            
            # Escrever CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['event', 'time', 'impact', 'currency', 'minutes_away'])
                writer.writeheader()
                writer.writerows(events)
            
            print(f"✅ Calendário exportado: {filename}")
            print(f"📊 Total de eventos: {len(events)}\n")
            
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 3. TESTAR SINAL DE TRADING
# ═══════════════════════════════════════════════════════════════════════

def test_trading_signal(action='BUY', confidence=0.75, adx=30, rsi=55):
    """Testa geração de sinal de trading"""
    print(f"🧪 Testando sinal: {action}\n")
    
    payload = {
        'technical_signal': action,
        'technical_score': confidence,
        'ema5': 2650.5,
        'ema15': 2648.0,
        'ema50': 2645.0,
        'adx': adx,
        'rsi': rsi,
        'current_price': 2650.0
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/signal",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("📊 RESULTADO DO SINAL")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"Sinal: {result.get('signal', 'N/A')}")
            print(f"Ação: {result.get('action', 'N/A')}")
            print(f"Confiança: {result.get('confidence', 0):.2f}%")
            print(f"Razão: {result.get('reason', 'N/A')}")
            
            if 'event_warning' in result and result['event_warning']:
                print(f"\n⚠️ ALERTA DE EVENTO:")
                print(f"   {result.get('event_name', 'Evento próximo')}")
                print(f"   Em {result.get('minutes_to_event', 0)} minutos")
                print(f"   Impacto: {result.get('impact_level', 'N/A')}")
            
            if 'news_sentiment' in result:
                print(f"\n📰 Sentimento: {result['news_sentiment']}")
            
            if 'components' in result:
                comps = result['components']
                print(f"\n🔍 COMPONENTES:")
                print(f"   Score Técnico: {comps.get('technical_score', 0):.1f}%")
                print(f"   Ajuste Notícias: {comps.get('news_adjustment', 0):+.1f}%")
                print(f"   Força Técnica: {comps.get('technical_strength', 0):.1f}%")
            
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Erro: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 4. ANALISAR NOTÍCIAS
# ═══════════════════════════════════════════════════════════════════════

def analyze_news(limit=10, sentiment_filter=None):
    """Analisa notícias recentes"""
    print("📰 Analisando notícias...\n")
    
    try:
        params = {'limit': limit}
        if sentiment_filter:
            params['sentiment'] = sentiment_filter
        
        response = requests.get(f"{SERVER_URL}/news", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            news_list = data.get('news', [])
            summary = data.get('sentiment_summary', {})
            overall = data.get('overall_sentiment', 'NEUTRAL')
            
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("📊 RESUMO DE SENTIMENTO")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"📈 Bullish: {summary.get('BULLISH', 0)}")
            print(f"📉 Bearish: {summary.get('BEARISH', 0)}")
            print(f"➖ Neutral: {summary.get('NEUTRAL', 0)}")
            print(f"\n🎯 Sentimento Geral: {overall}")
            print(f"📊 Total de notícias: {data.get('total', 0)}")
            print(f"🔄 Última atualização: {data.get('last_update', 'N/A')}")
            print(f"📡 API Calls: {data.get('api_calls_today', 0)} (Restam: {data.get('api_remaining', 0)})")
            
            if news_list:
                print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"📰 ÚLTIMAS {len(news_list)} NOTÍCIAS")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                for i, news in enumerate(news_list, 1):
                    sentiment_emoji = {
                        'BULLISH': '📈',
                        'BEARISH': '📉',
                        'NEUTRAL': '➖'
                    }.get(news['sentiment'], '❓')
                    
                    print(f"\n{i}. {sentiment_emoji} {news['sentiment']} (Score: {news['score']:.2f})")
                    print(f"   {news['title']}")
                    print(f"   Fonte: {news['source']} | Relevância: {news['relevance']:.0%}")
                    print(f"   Data: {news['time']}")
            
            print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 5. EXPORTAR HISTÓRICO DE SINAIS
# ═══════════════════════════════════════════════════════════════════════

def export_signal_history():
    """Exporta histórico de sinais para CSV"""
    print("📊 Exportando histórico de sinais...\n")
    
    try:
        response = requests.get(f"{SERVER_URL}/history?limit=200", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            signals = data.get('signals', [])
            stats = data.get('statistics', {})
            
            if not signals:
                print("⚠️ Nenhum sinal encontrado!")
                return
            
            # Nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{CSV_EXPORT_DIR}/signals_{timestamp}.csv"
            
            # Escrever CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'action', 'confidence', 'price'])
                writer.writeheader()
                writer.writerows(signals)
            
            print(f"✅ Histórico exportado: {filename}")
            print(f"📊 Total de sinais: {len(signals)}")
            print(f"\n📈 ESTATÍSTICAS:")
            print(f"   Confiança Média: {stats.get('average_confidence', 0):.2f}%")
            print(f"   Sinais BUY: {stats.get('buy_signals', 0)}")
            print(f"   Sinais SELL: {stats.get('sell_signals', 0)}")
            print(f"   Sinais WAIT: {stats.get('wait_signals', 0)}\n")
            
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 6. FORÇAR ATUALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════

def force_update():
    """Força atualização de dados"""
    print("🔄 Forçando atualização de dados...\n")
    
    try:
        response = requests.post(f"{SERVER_URL}/force-update", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Atualização iniciada!")
            print(f"   Calendário: {data.get('calendar', 'N/A')}")
            print(f"   Notícias: {data.get('news', 'N/A')}")
            print(f"   API Restante: {data.get('api_remaining', 0)}")
            print(f"   Timestamp: {data.get('timestamp', 'N/A')}\n")
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 7. VERIFICAR SAÚDE DO SISTEMA
# ═══════════════════════════════════════════════════════════════════════

def health_check():
    """Verifica saúde do sistema"""
    print("🏥 Verificando saúde do sistema...\n")
    
    endpoints = [
        ('/', 'Home'),
        ('/health', 'Health'),
        ('/status', 'Status'),
        ('/calendar', 'Calendar'),
        ('/news', 'News')
    ]
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("ENDPOINT                 STATUS          TEMPO")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    all_healthy = True
    
    for endpoint, name in endpoints:
        try:
            start = time.time()
            response = requests.get(f"{SERVER_URL}{endpoint}", timeout=5)
            elapsed = (time.time() - start) * 1000
            
            if response.status_code == 200:
                status = "✅ OK"
            else:
                status = f"⚠️ {response.status_code}"
                all_healthy = False
            
            print(f"{name:<24} {status:<15} {elapsed:.0f}ms")
            
        except Exception as e:
            print(f"{name:<24} ❌ ERRO         -")
            all_healthy = False
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if all_healthy:
        print("\n✅ Sistema totalmente operacional!\n")
    else:
        print("\n⚠️ Alguns problemas detectados!\n")


# ═══════════════════════════════════════════════════════════════════════
# 8. GERAR RELATÓRIO COMPLETO
# ═══════════════════════════════════════════════════════════════════════

def generate_report():
    """Gera relatório completo do sistema"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{LOGS_DIR}/report_{timestamp}.txt"
    
    print(f"📄 Gerando relatório completo...\n")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            # Cabeçalho
            f.write("╔═══════════════════════════════════════════════════════════════╗\n")
            f.write("║         🏆 GOLDAI PRO - RELATÓRIO DO SISTEMA              ║\n")
            f.write("╚═══════════════════════════════════════════════════════════════╝\n\n")
            f.write(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Status
            try:
                response = requests.get(f"{SERVER_URL}/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    f.write("STATUS DO SISTEMA\n")
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    f.write(json.dumps(data, indent=2))
                    f.write("\n\n")
            except:
                f.write("❌ Erro ao obter status\n\n")
            
            # Calendário
            try:
                response = requests.get(f"{SERVER_URL}/calendar", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    f.write("CALENDÁRIO ECONÔMICO\n")
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    for event in data.get('events', [])[:10]:
                        f.write(f"\n{event['event']}\n")
                        f.write(f"  Horário: {event['time']}\n")
                        f.write(f"  Impacto: {event['impact']}\n")
                        f.write(f"  Em {event['minutes_away']} minutos\n")
                    f.write("\n")
            except:
                f.write("❌ Erro ao obter calendário\n\n")
            
            # Notícias
            try:
                response = requests.get(f"{SERVER_URL}/news?limit=10", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    f.write("NOTÍCIAS RECENTES\n")
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    f.write(f"Sentimento Geral: {data.get('overall_sentiment', 'N/A')}\n\n")
                    for news in data.get('news', []):
                        f.write(f"{news['sentiment']} - {news['title'][:80]}...\n")
                        f.write(f"  Score: {news['score']} | Fonte: {news['source']}\n\n")
            except:
                f.write("❌ Erro ao obter notícias\n\n")
            
            # Histórico
            try:
                response = requests.get(f"{SERVER_URL}/history?limit=50", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    f.write("HISTÓRICO DE SINAIS\n")
                    f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    stats = data.get('statistics', {})
                    f.write(f"Total de sinais: {data.get('total_signals', 0)}\n")
                    f.write(f"Confiança média: {stats.get('average_confidence', 0):.2f}%\n")
                    f.write(f"Sinais BUY: {stats.get('buy_signals', 0)}\n")
                    f.write(f"Sinais SELL: {stats.get('sell_signals', 0)}\n")
                    f.write(f"Sinais WAIT: {stats.get('wait_signals', 0)}\n\n")
            except:
                f.write("❌ Erro ao obter histórico\n\n")
            
            f.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            f.write("FIM DO RELATÓRIO\n")
        
        print(f"✅ Relatório salvo: {filename}\n")
        
    except Exception as e:
        print(f"❌ Erro ao gerar relatório: {e}")


# ═══════════════════════════════════════════════════════════════════════
# MENU PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

def main_menu():
    """Menu principal de utilitários"""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║         🏆 GOLDAI PRO - FERRAMENTAS E UTILITÁRIOS         ║")
        print("╚═══════════════════════════════════════════════════════════════╝\n")
        print("1.  🔍 Monitor em Tempo Real")
        print("2.  📊 Exportar Calendário (CSV)")
        print("3.  🧪 Testar Sinal de Trading")
        print("4.  📰 Analisar Notícias")
        print("5.  📈 Exportar Histórico de Sinais")
        print("6.  🔄 Forçar Atualização")
        print("7.  🏥 Health Check")
        print("8.  📄 Gerar Relatório Completo")
        print("9.  ❌ Sair")
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        choice = input("\nEscolha uma opção: ").strip()
        
        print()
        
        if choice == '1':
            real_time_monitor()
        elif choice == '2':
            export_calendar_to_csv()
            input("\nPressione Enter para continuar...")
        elif choice == '3':
            print("Parâmetros do teste:")
            action = input("Ação (BUY/SELL) [BUY]: ").strip().upper() or 'BUY'
            conf = input("Confiança (0-1) [0.75]: ").strip() or '0.75'
            adx = input("ADX [30]: ").strip() or '30'
            rsi = input("RSI [55]: ").strip() or '55'
            print()
            test_trading_signal(action, float(conf), float(adx), float(rsi))
            input("\nPressione Enter para continuar...")
        elif choice == '4':
            limit = input("Quantas notícias? [10]: ").strip() or '10'
            sentiment = input("Filtrar sentimento (BULLISH/BEARISH/NEUTRAL) [Todos]: ").strip().upper() or None
            print()
            analyze_news(int(limit), sentiment)
            input("\nPressione Enter para continuar...")
        elif choice == '5':
            export_signal_history()
            input("\nPressione Enter para continuar...")
        elif choice == '6':
            force_update()
            input("\nPressione Enter para continuar...")
        elif choice == '7':
            health_check()
            input("\nPressione Enter para continuar...")
        elif choice == '8':
            generate_report()
            input("\nPressione Enter para continuar...")
        elif choice == '9':
            print("👋 Até logo!\n")
            break
        else:
            print("❌ Opção inválida!")
            time.sleep(1)


# ═══════════════════════════════════════════════════════════════════════
# EXECUÇÃO
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    try:
        # Verificar se servidor está acessível
        try:
            response = requests.get(f"{SERVER_URL}/health", timeout=3)
            if response.status_code != 200:
                print("⚠️ Servidor não está respondendo corretamente!")
                print(f"   Certifique-se de que está rodando em {SERVER_URL}\n")
                input("Pressione Enter para continuar mesmo assim...")
        except:
            print("❌ ERRO: Não foi possível conectar ao servidor!")
            print(f"   URL: {SERVER_URL}")
            print("\n   Certifique-se de que o servidor está rodando:")
            print("   python server.py\n")
            input("Pressione Enter para sair...")
            exit(1)
        
        # Iniciar menu
        main_menu()
        
    except KeyboardInterrupt:
        print("\n\n✅ Programa encerrado!\n")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}\n")