import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import LegalLayout from "@/components/layout/LegalLayout";

export const metadata: Metadata = {
  title: "Privacybeleid | Inversiq",
  description: "Lees hoe Inversiq omgaat met jouw persoonsgegevens conform de AVG.",
  openGraph: {
    title: "Privacybeleid | Inversiq",
    description: "Lees hoe Inversiq omgaat met jouw persoonsgegevens conform de AVG.",
    url: "https://inversiq.com/privacy",
    siteName: "Inversiq",
    locale: "nl_NL",
    type: "website",
  },
  alternates: {
    canonical: "https://inversiq.com/privacy",
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function PrivacyPage() {
  return (
    <>
      <Navbar />
      <LegalLayout
        badge="Juridisch"
        title="Privacybeleid"
        intro="Inversiq hecht veel waarde aan de bescherming van jouw persoonsgegevens. In dit privacybeleid leggen wij uit welke gegevens wij verwerken, waarom, en welke rechten jij hebt."
        lastUpdated="1 juni 2025"
      >

        <Section title="1. Wie zijn wij?">
          <p>
            Inversiq is een AI Automation Consultancy gevestigd in Nederland. Wij helpen bedrijven
            repetitieve en handmatige processen automatiseren met behulp van kunstmatige intelligentie,
            workflows en maatwerkoplossingen.
          </p>
          <ContactBlock />
        </Section>

        <Section title="2. Welke persoonsgegevens verwerken wij?">
          <p>Wij verwerken de volgende categorieën persoonsgegevens:</p>
          <ul>
            <li><strong>Contactformuliergegevens</strong> — naam, bedrijfsnaam, e-mailadres, telefoonnummer en de inhoud van je bericht.</li>
            <li><strong>Communicatiegegevens</strong> — e-mailcorrespondentie en berichten die je ons stuurt.</li>
            <li><strong>Websitegebruiksgegevens</strong> — IP-adres, browsertype, bezochte pagina's en tijdstip van bezoek (via analyticstools, zie artikel 7).</li>
            <li><strong>Zakelijke gegevens</strong> — informatie over jouw organisatie en bedrijfsprocessen die je met ons deelt in het kader van een opdracht.</li>
          </ul>
        </Section>

        <Section title="3. Op welke grondslag verwerken wij jouw gegevens?">
          <p>Wij verwerken jouw persoonsgegevens op basis van de volgende grondslagen:</p>
          <ul>
            <li><strong>Uitvoering van een overeenkomst</strong> — wanneer je een offerte aanvraagt of gebruik maakt van onze diensten.</li>
            <li><strong>Gerechtvaardigd belang</strong> — voor het beantwoorden van vragen via het contactformulier en voor de verbetering van onze website.</li>
            <li><strong>Toestemming</strong> — voor het plaatsen van niet-functionele cookies en voor het versturen van nieuwsbrieven (indien van toepassing).</li>
            <li><strong>Wettelijke verplichting</strong> — wanneer wij gehouden zijn gegevens te bewaren op basis van wet- en regelgeving.</li>
          </ul>
        </Section>

        <Section title="4. Waarvoor gebruiken wij jouw gegevens?">
          <p>Wij gebruiken jouw persoonsgegevens voor de volgende doeleinden:</p>
          <ul>
            <li>Het beantwoorden van jouw aanvraag via het contactformulier of per e-mail.</li>
            <li>Het plannen en uitvoeren van een demo of kennismakingsgesprek.</li>
            <li>Het opstellen en uitvoeren van offertes en overeenkomsten.</li>
            <li>Het leveren van onze consultancy- en automatiseringsdiensten.</li>
            <li>Het verbeteren van onze website en dienstverlening.</li>
            <li>Het voldoen aan wettelijke verplichtingen.</li>
          </ul>
        </Section>

        <Section title="5. Hoe lang bewaren wij jouw gegevens?">
          <p>
            Wij bewaren jouw persoonsgegevens niet langer dan noodzakelijk voor het doel waarvoor zij
            zijn verzameld, tenzij een langere bewaartermijn wettelijk verplicht is.
          </p>
          <ul>
            <li><strong>Contactformuliergegevens</strong> — maximaal 12 maanden na het laatste contact, tenzij een zakelijke relatie is ontstaan.</li>
            <li><strong>Klantgegevens en projectdossiers</strong> — 7 jaar na afronding van de opdracht (fiscale bewaarplicht).</li>
            <li><strong>Websiteanalytics</strong> — conform de bewaartermijnen van de betreffende analyticstools (doorgaans 14–26 maanden).</li>
          </ul>
        </Section>

        <Section title="6. Delen wij jouw gegevens met derden?">
          <p>
            Inversiq deelt jouw persoonsgegevens niet met derden voor commerciële doeleinden. Wij
            kunnen gegevens delen met:
          </p>
          <ul>
            <li><strong>Verwerkers</strong> — dienstverleners die namens ons gegevens verwerken, zoals hostingproviders en e-mailplatformen. Met al deze partijen hebben wij een verwerkersovereenkomst gesloten.</li>
            <li><strong>Wettelijke instanties</strong> — wanneer wij daartoe wettelijk verplicht zijn of wanneer dit noodzakelijk is om onze rechten te beschermen.</li>
          </ul>
          <p>
            Wij geven jouw gegevens nooit door aan landen buiten de Europese Economische Ruimte (EER)
            zonder dat daarvoor passende waarborgen bestaan.
          </p>
        </Section>

        <Section title="7. Cookies en analytics">
          <p>
            Onze website maakt gebruik van cookies. Cookies zijn kleine tekstbestandjes die bij een
            bezoek aan onze website op jouw apparaat worden opgeslagen.
          </p>
          <p>Wij onderscheiden de volgende typen cookies:</p>
          <ul>
            <li><strong>Functionele cookies</strong> — noodzakelijk voor het goed functioneren van de website. Deze cookies vereisen geen toestemming.</li>
            <li><strong>Analytische cookies</strong> — wij gebruiken anonieme statistieken om inzicht te krijgen in het gebruik van onze website. Wij streven ernaar deze volledig geanonimiseerd en privacyvriendelijk in te stellen.</li>
          </ul>
          <p>
            Je kunt cookies uitschakelen via de instellingen van jouw browser. Houd er rekening mee
            dat dit de werking van de website kan beïnvloeden.
          </p>
        </Section>

        <Section title="8. Jouw rechten">
          <p>Op grond van de Algemene Verordening Gegevensbescherming (AVG) heb je de volgende rechten:</p>
          <ul>
            <li><strong>Recht op inzage</strong> — je hebt het recht om te weten welke gegevens wij van jou verwerken.</li>
            <li><strong>Recht op rectificatie</strong> — je kunt onjuiste of onvolledige gegevens laten corrigeren.</li>
            <li><strong>Recht op verwijdering</strong> — in bepaalde gevallen heb je het recht jouw gegevens te laten verwijderen ("recht op vergetelheid").</li>
            <li><strong>Recht op beperking van de verwerking</strong> — je kunt verzoeken de verwerking van jouw gegevens tijdelijk stop te zetten.</li>
            <li><strong>Recht op dataportabiliteit</strong> — je kunt jouw gegevens in een gestructureerd, gangbaar formaat opvragen.</li>
            <li><strong>Recht van bezwaar</strong> — je kunt bezwaar maken tegen de verwerking op basis van gerechtvaardigd belang.</li>
            <li><strong>Recht op intrekking van toestemming</strong> — wanneer verwerking is gebaseerd op toestemming, kun je deze te allen tijde intrekken.</li>
          </ul>
          <p>
            Om een verzoek in te dienen, neem je contact op via <strong>info@inversiq.com</strong>.
            Wij reageren binnen 30 dagen op jouw verzoek. Je hebt ook het recht een klacht in te
            dienen bij de Autoriteit Persoonsgegevens via{" "}
            <a href="https://www.autoriteitpersoonsgegevens.nl" target="_blank" rel="noopener noreferrer">
              autoriteitpersoonsgegevens.nl
            </a>.
          </p>
        </Section>

        <Section title="9. Beveiliging">
          <p>
            Inversiq neemt passende technische en organisatorische maatregelen om jouw
            persoonsgegevens te beschermen tegen verlies, misbruik of ongeoorloofde toegang. Denk
            aan versleutelde verbindingen (HTTPS), toegangsbeveiliging en regelmatige evaluatie van
            onze beveiligingsmaatregelen.
          </p>
        </Section>

        <Section title="10. Wijzigingen in dit privacybeleid">
          <p>
            Inversiq kan dit privacybeleid van tijd tot tijd aanpassen. De meest actuele versie is
            altijd te vinden op deze pagina. Bij ingrijpende wijzigingen stellen wij je hiervan op
            de hoogte via e-mail of een melding op de website.
          </p>
        </Section>

        <Section title="11. Contact">
          <p>
            Heb je vragen over dit privacybeleid of over de manier waarop wij jouw
            persoonsgegevens verwerken? Neem dan contact met ons op:
          </p>
          <ContactBlock />
        </Section>

      </LegalLayout>
      <Footer />
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-xl font-semibold text-neutral-900 mb-4 tracking-tight">{title}</h2>
      <div className="flex flex-col gap-3 text-neutral-600 leading-relaxed text-[0.9375rem]">
        {children}
      </div>
    </section>
  );
}

function ContactBlock() {
  return (
    <div
      className="rounded-xl p-5 mt-2"
      style={{
        backgroundColor: "rgba(37,99,235,0.04)",
        border: "1px solid rgba(37,99,235,0.1)",
      }}
    >
      <p className="text-sm font-semibold text-neutral-800 mb-1">Inversiq</p>
      <p className="text-sm text-neutral-500">KvK: 42027564</p>
      <p className="text-sm text-neutral-500">Nederland</p>
      <a
        href="mailto:info@inversiq.com"
        className="text-sm font-medium"
        style={{ color: "#2563EB" }}
      >
        info@inversiq.com
      </a>
    </div>
  );
}
