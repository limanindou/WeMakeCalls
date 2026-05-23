import { Injectable, signal } from '@angular/core';
import { Client, IMessage } from '@stomp/stompjs';
import { Observable } from 'rxjs';
import { TimerMessage } from '../models/interfaces';
import SockJS from 'sockjs-client';

@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private client!: Client;
  connectionState = signal<'DISCONNECTED' | 'CONNECTING' | 'CONNECTED'>('DISCONNECTED');

  connect(): void {
    if (this.connectionState() === 'CONNECTED') return;

    this.connectionState.set('CONNECTING');

    this.client = new Client({
      webSocketFactory: () => new SockJS('http://localhost:5000/ws') as any,
      reconnectDelay: 5000,
      onConnect: () => {
        this.connectionState.set('CONNECTED');
      },
      onDisconnect: () => {
        this.connectionState.set('DISCONNECTED');
      },
      onStompError: (frame) => {
        console.error('STOMP error:', frame);
        this.connectionState.set('DISCONNECTED');
      }
    });

    this.client.activate();
  }

  disconnect(): void {
    if (this.client) {
      this.client.deactivate();
    }
    this.connectionState.set('DISCONNECTED');
  }

  subscribeToTimer(callId: string): Observable<TimerMessage> {
    return new Observable<TimerMessage>((subscriber) => {
      const subscription = this.client.subscribe(
        `/topic/call-timer/${callId}`,
        (message: IMessage) => {
          const timerMsg: TimerMessage = JSON.parse(message.body);
          subscriber.next(timerMsg);
        }
      );

      return () => {
        subscription.unsubscribe();
      };
    });
  }
}
