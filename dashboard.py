#!/usr/bin/env python3
"""
Dashboard Monitor para TraderIA - VERSÃO CORRIGIDA
Monitora o bot em tempo real com estatísticas reais
"""

import requests
import json
import time
from datetime import datetime, timedelta
from collections import deque
import os
import sys

class TraderIAMonitor:
    def __init__(self, server_url="http://127.0.0.1:5000"):
        self.server_url = server_url
        self.signals = deque(maxlen=50)
        self.daily_pips = 0
        self.session_start = datetime.now()
        self.last_signal_time = None
        
    def check_server(self):
        """Verifica se servidor está online"""
        try:
            response = requests.get(f"{self.server_url}/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return True, data
            return False, None
        except Exception as e:
            print(f"❌ Erro conexão servidor: {e}")
            return False, None
    
    def send_test_signal(self):
        """Envia sinal de teste para servidor"""
        try:
            test_data = {
                "symbol": "EURUSD",
                "account_balance": 10000,
                "equity": 10000,
                "current_price": 1.0850,
                "technical_signal": "NEUTRAL",
                "technical_score": 0.5
            }
            
            response = requests.post(
                f"{self.server_url}/signal",
                json=test_data,
                timeout=10
            )
            
            if response.status_code == 200:
                signal_data = response.json()
                signal_data['received_at'] = datetime.now().isoformat()
                return signal_data
            else:
                print(f"❌ Servidor retornou erro: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print("❌ Timeout ao conectar com servidor")
            return None
        except Exception as e:
            print(f"❌ Erro ao enviar teste: {e}")
            return None
    
    def clear_screen(self):
        """Limpa tela de forma compatível"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def format_dashboard(self, server_status, server_data=None):
        """Formata dashboard com informações reais"""
        uptime = datetime.now() - self.session_start
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        seconds = uptime.seconds % 60
        
        # Informações do servidor
        server_info = ""
        if server_status and server_data:
            news_count = server_data.get('news_count', 0)
            last_update = server_data.get('last_news_update', 'N/A')
            model_status = "✅" if server_data.get('model_loaded', False) else "❌"
            server_info = f"""
├─ Notícias Cache: {news_count}
├─ Última Atualização: {last_update}
├─ Modelo IA: {model_status}"""
        
        # ✅ CORREÇÃO: Condições simplificadas para evitar erro de sintaxe
        checklist_servidor = '✅' if server_status else '❌'
        checklist_sinais = '✅' if self.signals else '❌'
        
        sinais_ativos = any(s.get('action') in ['buy','sell'] for s in self.signals)
        checklist_ativos = '✅' if sinais_ativos else '❌'
        
        if server_status and server_data:
            checklist_ia = '✅' if server_data.get('model_loaded', False) else '❌'
            checklist_noticias = '✅' if server_data.get('news_count', 0) > 0 else '❌'
        else:
            checklist_ia = '❌'
            checklist_noticias = '❌'
        
        dashboard = f"""
╔════════════════════════════════════════════════════════════╗
║           🤖 TraderIA v2.0 - Monitor Dashboard             ║
╚════════════════════════════════════════════════════════════╝

📊 STATUS DO SERVIDOR
├─ URL: {self.server_url}
├─ Status: {'🟢 ONLINE' if server_status else '🔴 OFFLINE'}
├─ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
├─ Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}
{server_info}

🔧 ESTATÍSTICAS DA SESSÃO
├─ Total de Sinais: {len(self.signals)}
├─ Sinais Ativos (BUY/SELL): {len([s for s in self.signals if s.get('action') in ['buy', 'sell']])}
├─ Sinais HOLD: {len([s for s in self.signals if s.get('action') == 'hold'])}
├─ Score Médio: {self._calculate_avg_score():.2f}
└─ Confiança Média: {self._calculate_avg_confidence():.1f}%

📈 ÚLTIMOS SINAIS (mais recentes primeiro)
"""
        
        if self.signals:
            signals_list = list(self.signals)[-5:][::-1]
            
            for i, signal in enumerate(signals_list, 1):
                action = signal.get('action', 'hold').upper()
                score = signal.get('score', 0)
                confidence = signal.get('confidence', 'unknown')
                sentiment = signal.get('sentiment', 'N/A')
                news_source = signal.get('news_source', 'N/A')[:20]
                
                emoji = '🔵 BUY' if action == 'BUY' else '🔴 SELL' if action == 'SELL' else '➖ HOLD'
                time_str = self._format_time(signal.get('received_at'))
                
                dashboard += f"│ {i}. {emoji:8} | Score: {score:.2f} | Conf: {confidence:8}\n"
                dashboard += f"│     📰 {news_source} | 😊 {sentiment:8} | ⏰ {time_str}\n"
                
                if i < len(signals_list):
                    dashboard += "│    " + "-" * 50 + "\n"
        else:
            dashboard += "│ 🚫 Nenhum sinal recebido ainda...\n"

        dashboard += f"""
⚙️  CONFIGURAÇÕES RECOMENDADAS
├─ Score Mínimo: 0.75+
├─ Volume Base: 0.01
├─ SL: 30-50 pips | TP: 45-75 pips
├─ Intervalo: 60 segundos
└─ Peso Notícias: 60% | Técnico: 40%

🎯 CHECKLIST OPERACIONAL
├─ {checklist_servidor} Servidor respondendo
├─ {checklist_sinais} Sinais sendo recebidos
├─ {checklist_ativos} Sinais ativos gerados
├─ {checklist_ia} IA carregada
└─ {checklist_noticias} Notícias disponíveis

💡 AÇÕES RECOMENDADAS
├─ Verifique logs do cTrader para execuções
├─ Confirme conexão bot-servidor
├─ Monitore qualidade dos sinais
├─ Ajuste scores mínimos se necessário
└─ Registre trades manualmente para análise

╔════════════════════════════════════════════════════════════╗
║ Pressione CTRL+C para sair | Atualizando a cada 30s       ║
╚════════════════════════════════════════════════════════════╝
"""
        return dashboard
    
    def _format_time(self, timestamp_str):
        """Formata timestamp para display"""
        try:
            if timestamp_str:
                signal_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                now = datetime.now().replace(tzinfo=signal_time.tzinfo)
                diff = now - signal_time
                minutes = diff.seconds // 60
                return f"{minutes}min atrás" if minutes > 0 else "Agora"
        except:
            pass
        return "N/A"
    
    def _calculate_avg_score(self):
        """Calcula score médio dos sinais"""
        if not self.signals:
            return 0.0
        scores = [s.get('score', 0) for s in self.signals]
        return sum(scores) / len(scores)
    
    def _calculate_avg_confidence(self):
        """Calcula confiança média"""
        if not self.signals:
            return 0.0
        
        confidence_map = {
            'very_high': 95,
            'high': 80, 
            'medium': 60,
            'low': 30
        }
        
        conf_values = []
        for signal in self.signals:
            conf = signal.get('confidence', 'low')
            conf_values.append(confidence_map.get(conf, 30))
        
        return sum(conf_values) / len(conf_values) if conf_values else 0.0
    
    def run(self):
        """Loop de monitoramento principal"""
        print("🚀 Iniciando Monitor TraderIA...")
        print("📡 Conectando ao servidor...")
        time.sleep(2)
        
        signal_count = 0
        
        while True:
            try:
                self.clear_screen()
                
                # Verifica servidor
                server_online, server_data = self.check_server()
                
                signal_received = None
                if server_online:
                    # Envia sinal apenas a cada 5 ciclos (2.5 minutos)
                    if signal_count % 5 == 0:
                        print("🔄 Solicitando novo sinal do servidor...")
                        signal_received = self.send_test_signal()
                        if signal_received:
                            self.signals.append(signal_received)
                            self.last_signal_time = datetime.now()
                            print(f"✅ Sinal recebido: {signal_received.get('action', 'hold')} (Score: {signal_received.get('score', 0):.2f})")
                
                signal_count += 1
                
                # Mostra dashboard
                dashboard = self.format_dashboard(server_online, server_data)
                print(dashboard)
                
                # Mostra status da próxima atualização
                next_update = 30 if signal_count % 5 != 0 else 150
                print(f"⏰ Próxima atualização de sinal em: {next_update} segundos")
                
                # Aguarda 30 segundos
                time.sleep(30)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Finalizando monitor...")
                self._save_session()
                break
            except Exception as e:
                print(f"❌ Erro no monitor: {e}")
                time.sleep(10)
    
    def _save_session(self):
        """Salva dados da sessão para análise"""
        try:
            session_file = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            data = {
                "session_start": self.session_start.isoformat(),
                "session_end": datetime.now().isoformat(),
                "total_signals": len(self.signals),
                "server_url": self.server_url,
                "signals": list(self.signals)
            }
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"📁 Sessão salva em: {session_file}")
            print(f"📊 Use: python {sys.argv[0]} --analyze {session_file}")
            
        except Exception as e:
            print(f"❌ Erro ao salvar sessão: {e}")


class PerformanceAnalyzer:
    """Analisa performance dos sinais"""
    
    @staticmethod
    def analyze_signals(session_file):
        """Analisa arquivo de sinais da sessão"""
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print("\n📊 ANÁLISE DE PERFORMANCE - TRAderIA")
            print("=" * 60)
            
            signals = data.get('signals', [])
            if not signals:
                print("❌ Nenhum sinal para analisar")
                return
            
            # Análise por tipo de sinal
            buy_signals = [s for s in signals if s.get('action') == 'buy']
            sell_signals = [s for s in signals if s.get('action') == 'sell']
            hold_signals = [s for s in signals if s.get('action') == 'hold']
            
            total_signals = len(signals)
            
            print(f"\n📈 DISTRIBUIÇÃO DE SINAIS (Total: {total_signals})")
            print(f"├─ 🔵 BUY Signals: {len(buy_signals)} ({len(buy_signals)/total_signals*100:.1f}%)")
            print(f"├─ 🔴 SELL Signals: {len(sell_signals)} ({len(sell_signals)/total_signals*100:.1f}%)")
            print(f"└─ ➖ HOLD Signals: {len(hold_signals)} ({len(hold_signals)/total_signals*100:.1f}%)")
            
            # Análise de qualidade
            print(f"\n🎯 QUALIDADE DOS SINAIS")
            
            all_scores = [s.get('score', 0) for s in signals]
            print(f"├─ Score Médio: {sum(all_scores)/len(all_scores):.3f}")
            print(f"├─ Score Mínimo: {min(all_scores):.3f}")
            print(f"├─ Score Máximo: {max(all_scores):.3f}")
            print(f"└─ Sinais >0.75: {len([s for s in all_scores if s > 0.75])} ({len([s for s in all_scores if s > 0.75])/total_signals*100:.1f}%)")
            
            # Análise de confiança
            print(f"\n💪 NÍVEL DE CONFIANÇA")
            confidence_levels = {}
            for signal in signals:
                conf = signal.get('confidence', 'unknown')
                confidence_levels[conf] = confidence_levels.get(conf, 0) + 1
            
            for level, count in sorted(confidence_levels.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_signals) * 100
                print(f"├─ {level:12}: {count:2d} ({percentage:5.1f}%)")
            
            # Análise de sentimentos
            print(f"\n😊 ANÁLISE DE SENTIMENTO")
            sentiments = {}
            for signal in signals:
                sentiment = signal.get('sentiment', 'UNKNOWN')
                sentiments[sentiment] = sentiments.get(sentiment, 0) + 1
            
            for sentiment, count in sentiments.items():
                percentage = (count / total_signals) * 100
                print(f"├─ {sentiment:10}: {count:2d} ({percentage:5.1f}%)")
            
            # Fontes de notícias
            print(f"\n📰 FONTES DE NOTÍCIAS (Top 5)")
            sources = {}
            for signal in signals:
                source = signal.get('news_source', 'Desconhecida')
                if source and source != 'N/A':
                    sources[source] = sources.get(source, 0) + 1
            
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"├─ {source:20}: {count:2d}")
            
            print("\n" + "=" * 60)
            print(f"💡 Dica: Scores >0.75 são considerados de alta qualidade")
            print(f"📅 Sessão: {data.get('session_start', 'N/A')}")
            
        except FileNotFoundError:
            print(f"❌ Arquivo não encontrado: {session_file}")
        except Exception as e:
            print(f"❌ Erro ao analisar: {e}")


def main():
    """Função principal corrigida"""
    print("╔════════════════════════════════════════════╗")
    print("║   TraderIA Monitor & Analyzer v2.0         ║")
    print("║           (CORRIGIDO)                      ║")
    print("╚════════════════════════════════════════════╝\n")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--analyze":
        # Modo análise
        if len(sys.argv) > 2:
            PerformanceAnalyzer.analyze_signals(sys.argv[2])
        else:
            print("❌ Uso correto: python dashboard.py --analyze <arquivo_sessao.json>")
            print("💡 Arquivos de sessão: session_YYYYMMDD_HHMMSS.json")
    else:
        # Modo monitor
        monitor = TraderIAMonitor()
        try:
            monitor.run()
        except Exception as e:
            print(f"❌ Erro fatal: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()