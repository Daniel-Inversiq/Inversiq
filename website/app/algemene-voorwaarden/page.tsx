import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import LegalLayout from "@/components/layout/LegalLayout";

export const metadata: Metadata = {
  title: "Algemene voorwaarden | Inversiq",
  description: "De algemene voorwaarden van Inversiq voor AI automation consultancy diensten.",
  openGraph: {
    title: "Algemene voorwaarden | Inversiq",
    description: "De algemene voorwaarden van Inversiq voor AI automation consultancy diensten.",
    url: "https://inversiq.com/algemene-voorwaarden",
    siteName: "Inversiq",
    locale: "nl_NL",
    type: "website",
  },
  alternates: {
    canonical: "https://inversiq.com/algemene-voorwaarden",
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function AlgemeneVoorwaardenPage() {
  return (
    <>
      <Navbar />
      <LegalLayout
        badge="Juridisch"
        title="Algemene Voorwaarden"
        intro="Deze algemene voorwaarden zijn van toepassing op alle aanbiedingen, offertes en overeenkomsten tussen Inversiq en haar opdrachtgevers."
        lastUpdated="1 juni 2025"
      >

        <Section title="Artikel 1 — Definities">
          <ul>
            <li><strong>Inversiq</strong> — de besloten vennootschap Inversiq, gevestigd in Nederland, ingeschreven in het Handelsregister van de Kamer van Koophandel onder nummer 42027564.</li>
            <li><strong>Opdrachtgever</strong> — de natuurlijke persoon of rechtspersoon die met Inversiq een overeenkomst aangaat of wenst aan te gaan.</li>
            <li><strong>Diensten</strong> — alle werkzaamheden die Inversiq verricht in het kader van AI-automatisering, consultancy, implementatie en aanverwante activiteiten.</li>
            <li><strong>Overeenkomst</strong> — elke afspraak tussen Inversiq en Opdrachtgever tot het leveren van Diensten.</li>
            <li><strong>Offerte</strong> — een schriftelijk aanbod van Inversiq aan Opdrachtgever.</li>
          </ul>
        </Section>

        <Section title="Artikel 2 — Toepasselijkheid">
          <p>
            Deze algemene voorwaarden zijn van toepassing op alle aanbiedingen, offertes,
            werkzaamheden, overeenkomsten en leveringen van Diensten door Inversiq, tenzij
            uitdrukkelijk schriftelijk anders is overeengekomen.
          </p>
          <p>
            De toepasselijkheid van eventuele inkoop- of andere voorwaarden van Opdrachtgever wordt
            uitdrukkelijk van de hand gewezen.
          </p>
          <p>
            Indien één of meerdere bepalingen van deze voorwaarden nietig zijn of vernietigd worden,
            blijven de overige bepalingen volledig van toepassing.
          </p>
        </Section>

        <Section title="Artikel 3 — Offertes en totstandkoming overeenkomst">
          <p>
            Alle offertes van Inversiq zijn vrijblijvend en geldig gedurende 30 dagen na datum,
            tenzij anders vermeld. Inversiq is niet gebonden aan een offerte indien Opdrachtgever
            redelijkerwijs had kunnen begrijpen dat de offerte een vergissing of verschrijving bevat.
          </p>
          <p>
            Een overeenkomst komt tot stand op het moment dat Opdrachtgever een offerte schriftelijk
            (ook per e-mail) aanvaardt, of op het moment dat Inversiq een opdracht feitelijk uitvoert.
          </p>
          <p>
            Wijzigingen in de overeenkomst zijn slechts geldig indien schriftelijk overeengekomen
            door beide partijen.
          </p>
        </Section>

        <Section title="Artikel 4 — Uitvoering van de diensten">
          <p>
            Inversiq zal de Diensten naar beste inzicht en vermogen uitvoeren conform de eisen van
            goed vakmanschap. De verplichtingen van Inversiq betreffen een inspanningsverplichting,
            tenzij uitdrukkelijk een resultaatsverplichting is overeengekomen.
          </p>
          <p>
            Opdrachtgever draagt zorg voor tijdige en volledige aanlevering van alle gegevens,
            toegangen en medewerking die Inversiq nodig heeft voor de uitvoering van de Diensten.
            Vertraging als gevolg van het niet of niet tijdig aanleveren hiervan is voor rekening
            van Opdrachtgever.
          </p>
          <p>
            Inversiq is gerechtigd werkzaamheden te laten uitvoeren door derden, mits dit niet
            uitdrukkelijk schriftelijk is uitgesloten. Inversiq blijft verantwoordelijk voor de
            uitvoering.
          </p>
          <p>
            Indien de omvang of aard van de opdracht na totstandkoming van de overeenkomst wijzigt,
            zijn de gevolgen voor risico van Opdrachtgever. Inversiq zal Opdrachtgever tijdig
            informeren over eventuele meerkosten.
          </p>
        </Section>

        <Section title="Artikel 5 — Tarieven en betaling">
          <p>
            De overeengekomen tarieven luiden in euro's en zijn exclusief btw, tenzij uitdrukkelijk
            anders vermeld.
          </p>
          <p>
            Facturen dienen binnen 14 dagen na factuurdatum te worden voldaan, tenzij anders
            schriftelijk overeengekomen. Na het verstrijken van de betalingstermijn is Opdrachtgever
            van rechtswege in verzuim en is de wettelijke handelsrente verschuldigd.
          </p>
          <p>
            Inversiq is gerechtigd de uitvoering van werkzaamheden op te schorten indien een factuur
            na twee aanmaningen onbetaald blijft, onverminderd het recht op vergoeding van alle
            schade, kosten en rente.
          </p>
          <p>
            Bezwaren tegen facturen dienen binnen 14 dagen na factuurdatum schriftelijk te worden
            ingediend. Na deze termijn wordt de factuur geacht te zijn aanvaard.
          </p>
        </Section>

        <Section title="Artikel 6 — Intellectueel eigendom">
          <p>
            Alle intellectuele eigendomsrechten op door Inversiq ontwikkelde software, documentatie,
            methodieken, modellen en andere materialen berusten bij Inversiq, tenzij uitdrukkelijk
            schriftelijk anders is overeengekomen.
          </p>
          <p>
            Na volledige betaling verleent Inversiq aan Opdrachtgever een niet-exclusief,
            niet-overdraagbaar gebruiksrecht op de specifiek voor Opdrachtgever ontwikkelde
            maatwerkoplossingen, voor gebruik binnen de eigen organisatie.
          </p>
          <p>
            Opdrachtgever is niet gerechtigd door Inversiq geleverde producten of diensten te
            verveelvoudigen, openbaar te maken of door te leveren aan derden zonder voorafgaande
            schriftelijke toestemming van Inversiq.
          </p>
          <p>
            Inversiq behoudt het recht generieke kennis, methodieken en niet-vertrouwelijke
            technische oplossingen te gebruiken voor andere opdrachtgevers.
          </p>
        </Section>

        <Section title="Artikel 7 — Vertrouwelijkheid">
          <p>
            Beide partijen zijn verplicht tot geheimhouding van alle vertrouwelijke informatie die
            zij in het kader van de overeenkomst van elkaar of uit andere bronnen hebben verkregen.
            Informatie geldt als vertrouwelijk indien dit door de andere partij is medegedeeld of
            voortvloeit uit de aard van de informatie.
          </p>
          <p>
            De geheimhoudingsverplichting geldt niet voor informatie die algemeen bekend is of wordt
            zonder toedoen van de ontvangende partij, of waarvan openbaarmaking op grond van een
            wettelijke verplichting is vereist.
          </p>
        </Section>

        <Section title="Artikel 8 — Aansprakelijkheid">
          <p>
            De totale aansprakelijkheid van Inversiq voor directe schade is beperkt tot het bedrag
            dat in het kader van de betreffende overeenkomst door Opdrachtgever is betaald in de
            drie maanden voorafgaand aan de schadeveroorzakende gebeurtenis, met een maximum van
            €10.000 per gebeurtenis of reeks van samenhangende gebeurtenissen.
          </p>
          <p>
            Inversiq is nimmer aansprakelijk voor indirecte schade, waaronder begrepen maar niet
            beperkt tot gevolgschade, gederfde winst, gemiste besparingen, schade door
            bedrijfsstagnatie of verlies van gegevens.
          </p>
          <p>
            De aansprakelijkheidsbeperking geldt niet bij opzet of bewuste roekeloosheid van
            Inversiq of haar leidinggevenden.
          </p>
          <p>
            Opdrachtgever vrijwaart Inversiq voor aanspraken van derden die schade lijden in verband
            met de uitvoering van de overeenkomst, voor zover die schade aan Opdrachtgever is toe
            te rekenen.
          </p>
        </Section>

        <Section title="Artikel 9 — Overmacht">
          <p>
            Inversiq is niet gehouden tot nakoming van enige verplichting indien nakoming redelijkerwijs
            niet gevergd kan worden als gevolg van overmacht. Onder overmacht wordt verstaan: elke
            omstandigheid buiten de macht van Inversiq die nakoming van de overeenkomst verhindert,
            waaronder storingen bij derden, internetstoringen, overheidsmaatregelen, pandemieën en
            natuurrampen.
          </p>
          <p>
            Indien een overmachtsituatie langer dan 60 dagen duurt, heeft elk der partijen het recht
            de overeenkomst schriftelijk te ontbinden, zonder verplichting tot schadevergoeding.
          </p>
        </Section>

        <Section title="Artikel 10 — Duur en beëindiging">
          <p>
            De overeenkomst wordt aangegaan voor de duur zoals vermeld in de offerte of
            opdrachtbevestiging. Bij projectopdrachten eindigt de overeenkomst na oplevering en
            definitieve acceptatie.
          </p>
          <p>
            Elk der partijen kan de overeenkomst schriftelijk opzeggen met inachtneming van een
            opzegtermijn van 30 dagen, tenzij anders overeengekomen.
          </p>
          <p>
            Inversiq is gerechtigd de overeenkomst met onmiddellijke ingang te ontbinden indien:
          </p>
          <ul>
            <li>Opdrachtgever in staat van faillissement wordt verklaard of surseance van betaling aanvraagt;</li>
            <li>Opdrachtgever zijn betalingsverplichtingen niet nakomt en na aanmaning in gebreke blijft;</li>
            <li>Opdrachtgever zijn overige verplichtingen uit de overeenkomst niet nakomt en na schriftelijke ingebrekestelling nalatig blijft.</li>
          </ul>
          <p>
            Bij beëindiging van de overeenkomst zijn reeds gefactureerde bedragen voor verrichte
            werkzaamheden onmiddellijk opeisbaar.
          </p>
        </Section>

        <Section title="Artikel 11 — Wijziging van de voorwaarden">
          <p>
            Inversiq behoudt zich het recht voor deze algemene voorwaarden te wijzigen. Wijzigingen
            worden ten minste 30 dagen voor inwerkingtreding schriftelijk of per e-mail medegedeeld.
            Indien Opdrachtgever niet akkoord gaat, kan hij de overeenkomst beëindigen vóór de
            ingangsdatum van de wijziging.
          </p>
        </Section>

        <Section title="Artikel 12 — Toepasselijk recht en geschillen">
          <p>
            Op alle rechtsverhoudingen tussen Inversiq en Opdrachtgever is uitsluitend Nederlands
            recht van toepassing.
          </p>
          <p>
            Geschillen worden bij voorkeur in onderling overleg opgelost. Indien partijen er niet
            in slagen een geschil in onderling overleg op te lossen, wordt het voorgelegd aan de
            bevoegde rechter in het arrondissement waar Inversiq is gevestigd, tenzij de wet
            dwingend een andere rechter voorschrijft.
          </p>
        </Section>

        <Section title="Artikel 13 — Contact">
          <p>Voor vragen over deze algemene voorwaarden kunt u contact opnemen met:</p>
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
