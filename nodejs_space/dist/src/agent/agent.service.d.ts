import { SupabaseService, Cuidador } from '../common/supabase.service';
import { OpenRouterService } from '../common/openrouter.service';
export declare class AgentService {
    private readonly db;
    private readonly llm;
    constructor(db: SupabaseService, llm: OpenRouterService);
    handleMessage(phone: string, body: string): Promise<{
        reply: string;
        cuidador: Cuidador;
        intent: string;
        pessoa_cuidada_id: string | null;
    }>;
    private handleOnboarding;
}
