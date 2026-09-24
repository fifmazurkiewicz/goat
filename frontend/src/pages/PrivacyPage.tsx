import { Link } from "react-router-dom";

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2"><h2 className="text-xl font-semibold">{title}</h2><div className="space-y-2 text-sm leading-6 text-muted-foreground">{children}</div></section>
);

export default function PrivacyPage() {
  return (
    <main className="mx-auto min-h-dvh max-w-3xl space-y-8 px-4 py-10 sm:py-16">
      <div><Link to="/login" className="text-sm underline">← Wróć do logowania</Link><h1 className="mt-5 text-3xl font-bold">Polityka prywatności</h1><p className="mt-2 text-sm text-muted-foreground">Ostatnia aktualizacja: 24 września 2026 r.</p></div>
      <Section title="Administrator i kontakt"><p>Administratorem danych w aplikacji Goat jest operator aplikacji. W sprawach dotyczących prywatności napisz na <a className="underline" href="mailto:fmazurkiewicz@gmail.com">fmazurkiewicz@gmail.com</a>.</p></Section>
      <Section title="Jakie dane przetwarzamy"><p>Przetwarzamy dane konta, nick, profil coachingowy, wiadomości i konsultacje w czacie, persony, wyniki, plany, ustawienia zgód oraz techniczne dane bezpieczeństwa. Profil i rozmowy mogą zawierać dane dotyczące zdrowia, jeżeli je podasz.</p><p>Podawaj tylko dane potrzebne do coachingu. Nie wpisuj danych innych osób ani zbędnych informacji identyfikujących.</p></Section>
      <Section title="Cele i podstawy"><p>Dane konta i treści przetwarzamy, aby świadczyć usługę, zabezpieczać ją i realizować Twoje żądania. Dane dotyczące zdrowia przetwarzamy na podstawie Twojej wyraźnej zgody. Możesz ją wycofać w Ustawieniach; nie wpływa to na zgodność wcześniejszego przetwarzania.</p></Section>
      <Section title="AI i odbiorcy danych"><p>Odpowiedzi i plany są generowane z użyciem modeli AI przez OpenRouter. Pełna treść coachingu — w tym wiadomości, kontekst profilu, wyniki, plan i wywołania narzędzi — może być wysyłana do Langfuse Cloud, aby diagnozować działanie i niezawodność AI. Aplikacja korzysta także z Supabase (baza i logowanie), Render (API), Vercel (interfejs), Cloudflare (DNS i bezpieczeństwo) oraz Google, gdy logujesz się przez Google.</p><p>Odpowiedzi AI mogą być błędne. Goat nie diagnozuje, nie leczy i nie zastępuje lekarza.</p></Section>
      <Section title="Czas przechowywania i bezpieczeństwo"><p>Profil, persony, wyniki i plany przechowujemy do usunięcia ich przez Ciebie albo do usunięcia konta. Rozmowy są automatycznie usuwane po 365 dniach od ostatniej aktualizacji, zakończone techniczne zadania generowania po 30 dniach, a treść fragmentów zapisanych na potrzeby moderacji po 90 dniach. Historia udzielonych i wycofanych zgód jest przechowywana do usunięcia konta w celu rozliczalności.</p><p>Kopie zapasowe dostawców mogą wygasać później, zgodnie z ich cyklem technicznym, i nie są dostępne w zwykłym działaniu aplikacji.</p></Section>
      <Section title="Twoje prawa"><p>Możesz uzyskać dostęp do danych, sprostować je, pobrać kopię, ograniczyć przetwarzanie, wycofać zgodę lub usunąć konto. Część tych działań wykonasz w Ustawieniach, a w pozostałych sprawach skontaktuj się z administratorem. Możesz także złożyć skargę do Prezesa UODO.</p></Section>
      <p className="border-t pt-6 text-sm"><Link className="underline" to="/terms">Warunki korzystania</Link></p>
    </main>
  );
}
