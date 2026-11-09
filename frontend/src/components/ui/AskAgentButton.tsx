import { MessageSquareText } from "lucide-react";
import { askAgentAbout } from "@/lib/agentBridge";

/** Abre o painel do agente com a pergunta pré-preenchida (não envia; o operador revisa e envia). */
export function AskAgentButton({ question, subject }: { question: string; subject: string }) {
  const name = `Perguntar ao agente sobre ${subject}`;
  return (
    <button
      type="button"
      className="btn-ghost px-2 py-1 text-meta max-lg:min-h-11"
      aria-label={name}
      title={name}
      onClick={() => askAgentAbout(question)}
    >
      <MessageSquareText className="size-3.5 text-series" aria-hidden /> Perguntar
    </button>
  );
}
