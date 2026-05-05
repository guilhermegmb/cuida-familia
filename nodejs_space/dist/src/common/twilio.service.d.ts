export declare class TwilioService {
    validateSignature(signature: string | undefined, url: string, params: Record<string, any>): boolean;
    twiml(message: string): string;
}
