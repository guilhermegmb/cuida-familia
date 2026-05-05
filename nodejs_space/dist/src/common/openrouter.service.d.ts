export interface ChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}
export declare class OpenRouterService {
    private readonly url;
    private readonly fallback;
    chat(messages: ChatMessage[]): Promise<string>;
}
