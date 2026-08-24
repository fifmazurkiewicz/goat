import { UserProfileForm } from "@/components/profile/UserProfileForm";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";

/**
 * `/profile` — view and manual edit of `user_profile` (ADR-11).
 * The main path for filling in data remains conversational (`update_user_profile` in chat).
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
