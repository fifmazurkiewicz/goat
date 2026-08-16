import { UserProfileForm } from "@/components/profile/UserProfileForm";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";

/**
 * `/profile` — podgląd i ręczna edycja `user_profile` (ADR-11).
 * Główna ścieżka uzupełniania pozostaje konwersacyjna (`update_user_profile` w czacie).
 */
export default function ProfilePage() {
  return (
    <div className={`${PAGE_SHELL_CLASS} max-w-4xl`}>
      <h1 className={PAGE_TITLE_CLASS}>Profil</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        Dane, które Goat i Twoje persony pamiętają między rozmowami — bez powtarzania wagi, celu czy
        kontuzji przy każdej wiadomości.
      </p>

      <div className="mt-6">
        <UserProfileForm />
      </div>
    </div>
  );
}
