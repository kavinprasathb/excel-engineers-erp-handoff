import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { AppearanceCard } from "./AppearanceCard";
import { CompanyCard } from "./CompanyCard";
import { LetterheadCard } from "./LetterheadCard";
import { QuotationTermsCard } from "./QuotationTermsCard";
import { QuotationSpecsCard } from "./QuotationSpecsCard";
import { PasswordCard } from "./PasswordCard";

/**
 * Separate cards, each saving on its own. A single page-wide Save would mean a
 * failed password change could roll back an unrelated GST edit, and the user
 * would have no way to tell which half went through.
 */
export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Company details, security and appearance." />
      <PageBody>
        <div className="max-w-2xl space-y-4">
          <CompanyCard />
          <LetterheadCard />
          <QuotationTermsCard />
          <QuotationSpecsCard />
          <PasswordCard />
          <AppearanceCard />
        </div>
      </PageBody>
    </>
  );
}
