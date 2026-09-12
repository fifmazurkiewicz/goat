import { Link } from "react-router-dom";

export default function TermsPage() {
  return (
    <main className="mx-auto min-h-dvh max-w-3xl space-y-6 px-4 py-10 sm:py-16">
      <Link to="/login" className="text-sm underline">← Wróć do logowania</Link>
      <h1 className="text-3xl font-bold">Warunki korzystania z Goat</h1>
      <p className="text-sm text-muted-foreground">Ostatnia aktualizacja: 12 września 2026 r.</p>
      <div className="space-y-5 text-sm leading-6 text-muted-foreground">
        <p>Goat jest narzędziem coachingowym wspieranym przez generatywną AI. Treści mają charakter informacyjny i mogą zawierać błędy. Nie są diagnozą, poradą medyczną ani zamiennikiem kontaktu z lekarzem lub innym specjalistą.</p>
        <p>W nagłej sytuacji zdrowotnej skontaktuj się z numerem alarmowym 112. Nie polegaj na aplikacji przy decyzjach wymagających pilnej lub profesjonalnej oceny medycznej.</p>
        <p>Dbaj o bezpieczeństwo konta i podawaj prawdziwe informacje tylko w zakresie potrzebnym do coachingu. Nie przesyłaj danych innych osób, treści bezprawnych ani poufnych danych, do których nie masz prawa.</p>
        <p>Możemy ograniczyć dostęp, gdy jest to konieczne dla bezpieczeństwa lub prawidłowego działania usługi. W sprawach dotyczących usługi skontaktuj się przez <a className="underline" href="mailto:fmazurkiewicz@gmail.com">fmazurkiewicz@gmail.com</a>.</p>
      </div>
      <p className="border-t pt-6 text-sm"><Link className="underline" to="/privacy">Polityka prywatności</Link></p>
    </main>
  );
}
