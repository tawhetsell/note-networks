#!/usr/bin/env python3
"""
Generate atomic markdown notes in notes/ covering every Federalist and
Anti-Federalist paper with a confirmed or best-estimate SCOTUS citation.

Corpus rationale
----------------
Federalist papers (~56):  Top-30 from Lupu (Constitutional Commentary, 1998)
  plus additional papers identified through Corley/Howard/Nixon (Political
  Research Quarterly, 2005), Smith (UCLA Law Review, 2005), and Melton
  (Kentucky Law Journal, 1996/2001/2007 citation lists).  Papers covering
  only narrow legislative mechanics with no constitutional litigation surface
  (e.g. #18-21, #25-28 on appropriations detail, #34-36) are excluded.

Anti-Federalist papers (~11):  Papers identified by Zelinsky, "Misunderstanding
  the Anti-Federalist Papers" (Alabama Law Review, 2013) as appearing in SCOTUS
  opinions post-1981, supplemented by Garcia v. San Antonio (1985) and Heller
  (2008) citation trails.  AF citations increased sharply after Storing's
  Complete Anti-Federalist (1981) made the full corpus accessible to clerks.

This list is labeled best-estimate, not guaranteed complete.  The definitive
source is Melton's Shepard's-style guide (KLJ Vol. 85, 1996) which requires
law-library access.

Usage: python tools/seed_from_fed.py
"""

import json
import re
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
NOTES = REPO / "notes"
RAW   = REPO / "federalist_papers.json"   # optional; from fed_papers_fetch.py

# ---------------------------------------------------------------------------
# Note data.
# Each entry: (id, speaker, source, tags, body)
# speaker = HAMILTON | MADISON | JAY  (Federalist)
#           BRUTUS | FEDERAL_FARMER | CENTINEL | CATO  (Anti-Federalist)
# ---------------------------------------------------------------------------
NOTES_DATA = [

    # ================================================================
    # FEDERALIST PAPERS — ordered by paper number
    # ================================================================

    ("fed-001", "HAMILTON", "Federalist #1",
     ["union", "ratification", "introduction", "republic"],
     "Can mankind establish good government by reflection and choice, or must "
     "they forever depend on accident and force? Hamilton opens the series by "
     "framing ratification as the test of that question — and warns that those "
     "who profit from disunion will be the Constitution's loudest enemies."),

    ("fed-002", "JAY", "Federalist #2",
     ["union", "foreign-danger", "people", "providence"],
     "Providence gave this connected country to a united people sharing language, "
     "ancestry, and interests. Disunion invites foreign powers to exploit rivalries "
     "among quarreling states. One federal government is better positioned than "
     "thirteen separate ones to negotiate treaties and repel threats."),

    ("fed-003", "JAY", "Federalist #3",
     ["union", "foreign-danger", "treaties", "war", "justice"],
     "The federal government is more likely than individual states to honor "
     "treaties and avoid just causes for war. State governments, subject to local "
     "passions and particular interests, will be tempted to violate treaties for "
     "parochial advantage. A single national government with national perspective "
     "can apply consistent, dispassionate judgment to foreign relations. Cited in "
     "foreign affairs and treaty power cases."),

    ("fed-009", "HAMILTON", "Federalist #9",
     ["union", "faction", "republic", "confederacy"],
     "Montesquieu's objection — that republics must be small — is answered by the "
     "compound republic. The science of politics has advanced: balanced government, "
     "legislative checks, independent judiciary, representation. A confederate "
     "republic (a union of republics) preserves republican liberty while achieving "
     "the security of a larger state. The extended sphere tames faction rather than "
     "aggravating it."),

    ("fed-010", "MADISON", "Federalist #10",
     ["faction", "republic", "democracy", "liberty", "representation", "union"],
     "The mortal disease of popular government is faction — citizens united by "
     "passion or interest adverse to the rights of others. Its causes are sown in "
     "human nature and cannot be removed without destroying liberty. The only cure "
     "is to control faction's effects. In a pure democracy a passionate majority "
     "rules directly; no cure exists. A republic interposes representatives who "
     "refine popular sentiment. The decisive advantage is the extended sphere: in a "
     "large republic, more candidates dilute the risk of an unfit majority; diverse "
     "interests make coordinated faction harder to assemble. Size, "
     "counterintuitively, protects liberty."),

    ("fed-011", "HAMILTON", "Federalist #11",
     ["commerce", "navigation", "union", "trade", "federal"],
     "A unified America can negotiate commercial treaties from strength. Divided "
     "into competing states, Europe plays American ports against each other, "
     "extracting favorable terms none could resist individually. Federal control "
     "of navigation and trade policy enables retaliatory measures that secure "
     "mutual respect. Hamilton envisions the United States eventually becoming a "
     "naval power through unified commercial policy — impossible under the "
     "Articles. Cited in commerce clause and federal trade power cases."),

    ("fed-014", "MADISON", "Federalist #14",
     ["republic", "democracy", "territory", "representation"],
     "Distinguishes republic — government by representatives — from pure democracy "
     "— government by citizens in assembly. America's vast territory is navigable "
     "by roads and rivers; representatives travel to the capital, not all citizens. "
     "The size objection is answered by the very nature of representation. Cited "
     "in cases addressing the scope of federal legislative power over large "
     "geographic areas."),

    ("fed-015", "HAMILTON", "Federalist #15",
     ["union", "government", "law", "states", "articles"],
     "The Articles of Confederation are fatally defective: federal law operates on "
     "states, not individuals. Law that cannot reach individuals must rely on "
     "state compliance, which is inconsistent. Armies and courts act on persons, "
     "not political bodies. This structural flaw requires replacing — not merely "
     "patching — the existing government. The Confederation is not a government "
     "at all; it is a treaty among sovereigns."),

    ("fed-016", "HAMILTON", "Federalist #16",
     ["government", "law", "states", "coercion", "union", "individuals"],
     "The only alternative to a government that reaches individuals directly is "
     "military coercion of states. Coercing a state as a political body means war; "
     "armies cannot distinguish innocent citizens from delinquent governments. A "
     "federal government that operates through courts and laws on individual "
     "persons avoids this fatal dilemma. The Constitution's design — federal law "
     "binding on individuals — is the structural solution. Cited in commandeering "
     "and anti-commandeering cases including Printz v. United States."),

    ("fed-017", "HAMILTON", "Federalist #17",
     ["states", "federal", "power", "government", "people", "union"],
     "The federal government will not encroach on state powers because citizens' "
     "daily concerns are entirely local: property rights, personal security, family "
     "matters. State governments, being closer to the people, will command greater "
     "affection and loyalty than a distant federal authority. Federal power over "
     "war, commerce, and revenue leaves all ordinary governance to the states. The "
     "gravitational pull of local attachment is the structural check that prevents "
     "federal absorption of state functions."),

    ("fed-022", "HAMILTON", "Federalist #22",
     ["union", "ratification", "people", "commerce", "military"],
     "Foreign treaties, armies, and interstate commerce all require a single federal "
     "voice. Ratification must rest on the people directly — not on state "
     "legislatures susceptible to local interests — or the new government inherits "
     "the same fatal dependence on state consent as the Articles."),

    ("fed-023", "HAMILTON", "Federalist #23",
     ["military", "federal", "power", "government", "union", "defense"],
     "The federal government must possess full and unlimited power over national "
     "defense. The means of national security cannot be limited in advance because "
     "threats are unlimited and unpredictable. A government forbidden to raise "
     "armies adequate to the danger is no government at all. This is the "
     "foundational argument for a strong federal military establishment over "
     "reliance on state militias for national security."),

    ("fed-027", "HAMILTON", "Federalist #27",
     ["states", "federal", "law", "government", "constitution", "union"],
     "State officers take oaths to support the federal Constitution; they "
     "administer federal law at the local level. Regular operation of the federal "
     "government through and alongside state governments will build popular "
     "attachment to federal authority. Federal law reaches individuals directly — "
     "it does not depend on state mediation. This integration of state and federal "
     "government ensures allegiance from both directions."),

    ("fed-029", "HAMILTON", "Federalist #29",
     ["militia", "military", "federal", "states", "defense", "liberty"],
     "A well-regulated militia requires federal organization and training; leaving "
     "militia regulation entirely to states produces an ineffective defense. "
     "Hamilton defends the idea of a select, trained militia over the impractical "
     "fantasy of arming every citizen for regular military readiness. The standing "
     "army is not a threat as long as the militia is properly maintained as a "
     "counterweight. Cited extensively in District of Columbia v. Heller (2008) "
     "and McDonald v. City of Chicago (2010) on the Second Amendment."),

    ("fed-032", "HAMILTON", "Federalist #32",
     ["taxation", "states", "federal", "power", "concurrent", "supremacy"],
     "States and the federal government may both tax the same objects — concurrent "
     "taxation is constitutional and practical. Federal supremacy operates only "
     "where a direct textual collision exists; mere concurrent power is not "
     "collision. States retain full taxing authority except for import and export "
     "duties explicitly denied by Article I."),

    ("fed-033", "HAMILTON", "Federalist #33",
     ["necessary-proper", "supremacy", "federal", "power", "law", "states"],
     "The necessary and proper clause is merely declaratory of an implied power "
     "already inherent in any legislative grant. The supremacy clause means only "
     "that valid federal law overrides conflicting state law — it confers no new "
     "substantive power. Alarm about either clause is misplaced: a law not "
     "warranted by the enumerated grants will not be supreme; only legitimate "
     "exercises of federal power carry supremacy."),

    ("fed-037", "MADISON", "Federalist #37",
     ["convention", "government", "republic", "compromise", "stability"],
     "The first constructive Publius essay: Madison marvels at the Convention's "
     "achievement. The delegates faced unprecedented difficulty — blending national "
     "and federal elements, balancing energy with liberty, stability with "
     "accountability, using political language too imprecise for so novel a task. "
     "No human document is perfect; the Constitution should be judged against "
     "realistic alternatives, not an impossible standard of perfection."),

    ("fed-038", "MADISON", "Federalist #38",
     ["constitution", "articles", "government", "objections", "reform"],
     "The objections to the Constitution are mutually contradictory: critics "
     "simultaneously allege too much federal power and too little. Madison surveys "
     "the genuine defects of the Articles that critics ignore — no revenue, no "
     "army, no commercial policy, no treaty enforcement — and asks how the "
     "contradictory objections could simultaneously be satisfied. Any reform "
     "serious enough to fix the Articles would face the same objections now "
     "leveled at the Constitution."),

    ("fed-039", "MADISON", "Federalist #39",
     ["republic", "federalism", "people", "states", "national"],
     "The Constitution is republican: authority derives from the people, not a "
     "privileged order. The new government is partly national (operates directly "
     "on individuals), partly federal (states are constituent units). Ratification "
     "is federal; operation is national; amendment is mixed. Neither purely "
     "national nor purely federal — it is a new compound form."),

    ("fed-040", "MADISON", "Federalist #40",
     ["convention", "constitution", "authority", "people", "republic"],
     "The Convention exceeded its formal mandate — amend the Articles — but acted "
     "within the spirit of the people's instruction: create an effective national "
     "government. Where the letter and spirit of an authorization diverge, spirit "
     "controls. The people, not the Confederation Congress, are the ultimate "
     "authority; they can ratify whatever frame their delegates propose. This "
     "paper is the principal defense of the Convention's authority to propose an "
     "entirely new frame of government."),

    ("fed-041", "MADISON", "Federalist #41",
     ["federal", "power", "defense", "commerce", "general-welfare", "constitution"],
     "Are the powers granted to the federal government appropriate and safe? "
     "Madison argues the general welfare clause does not confer unlimited "
     "legislative power — it is a summary heading for the specific enumerated "
     "powers that follow. Military and commercial powers are not dangerous grants "
     "but necessities: a government that cannot defend its territory or regulate "
     "commerce is not a government. The question is not whether powers might be "
     "abused but whether they are indispensable."),

    ("fed-042", "MADISON", "Federalist #42",
     ["commerce", "treaties", "foreign", "interstate", "privileges", "union"],
     "Madison addresses federal powers over foreign intercourse and interstate "
     "relations. The commerce clause encompasses foreign trade, interstate "
     "commerce, and Indian trade under one coherent federal power — eliminating "
     "the conflicts and retaliations that plagued commerce under the Articles. "
     "The privileges and immunities clause ensures citizens receive equal treatment "
     "in every state. The law of nations, treaties, and extradition are brought "
     "under consistent federal authority. Cited by SCOTUS more times than any "
     "other paper in the series according to empirical citation studies."),

    ("fed-043", "MADISON", "Federalist #43",
     ["constitution", "amendment", "states", "republic", "government", "ratification"],
     "Madison surveys miscellaneous constitutional powers: the guarantee of "
     "republican government to every state, admission of new states, the federal "
     "district for the capital, Article V's amendment procedure, and Article VII's "
     "ratification rule. He defends the amendment process as appropriately "
     "balanced — neither so easy as to invite instability nor so difficult as to "
     "prevent necessary corrections."),

    ("fed-044", "MADISON", "Federalist #44",
     ["necessary-proper", "constitution", "federal", "power", "states", "contracts"],
     "The prohibitions on state impairment of contracts protect creditors and "
     "maintain commercial confidence. The necessary and proper clause is "
     "unavoidable: without it, every subsidiary power would require explicit "
     "enumeration — a labyrinthine impossibility no legislature could anticipate. "
     "The clause grants implied powers appropriate to each enumerated end. If "
     "Congress abuses it, the remedy is political — elections and constitutional "
     "amendment — not judicial nullification of all implied powers."),

    ("fed-045", "MADISON", "Federalist #45",
     ["states", "federal", "power", "people", "union"],
     "State governments will remain dominant. Citizens identify primarily with "
     "their states; state officers vastly outnumber federal officers; local "
     "concerns preoccupy most voters. The enumerated federal powers are few and "
     "defined; the residual state powers are numerous and indefinite. The "
     "sacrifice of state authority to the Union is real but modest compared to "
     "the benefits of peace, commerce, and collective defense."),

    ("fed-046", "MADISON", "Federalist #46",
     ["states", "federal", "power", "resistance", "people", "liberty"],
     "State and federal governments are both agents of the people — not rivals in "
     "a zero-sum contest. If the federal government overreaches, states have "
     "tools: legislative obstruction, popular resistance, coordinated opposition. "
     "The people's attachment to their states provides an institutional "
     "counterweight. Madison describes potential state resistance to "
     "unconstitutional federal acts as a natural political check — not a formal "
     "legal doctrine."),

    ("fed-047", "MADISON", "Federalist #47",
     ["separation-of-powers", "liberty", "government", "executive", "legislature"],
     "Separation of powers does not require total separation — only that no single "
     "branch controls another entirely. Montesquieu's maxim, properly read, allows "
     "blending. Britain's constitution — Montesquieu's own model — blends the "
     "branches substantially. Some interpenetration is necessary for each branch "
     "to check the others; absolute separation would leave each powerless against "
     "encroachment."),

    ("fed-048", "MADISON", "Federalist #48",
     ["separation-of-powers", "liberty", "legislature", "encroachment", "government"],
     "Paper barriers alone cannot contain legislative encroachment. Each "
     "department must have actual constitutional means — not just parchment "
     "declarations — to resist the ambitions of the others. The legislature, "
     "drawing its power from the people, is the branch most likely to aggrandize "
     "itself; the constitution must arm the other departments to resist."),

    ("fed-049", "MADISON", "Federalist #49",
     ["constitution", "stability", "convention", "people", "government"],
     "Jefferson's proposal — periodic constitutional conventions to correct "
     "encroachments — would unsettle government rather than stabilize it. "
     "Frequent appeals to the people would undermine judicial precedent, "
     "destabilize constitutional meaning, and reduce the Constitution to a "
     "political document subject to factional revision. The proper remedy is "
     "structural: separated powers that check each other internally, not external "
     "appeals to a temporary popular majority."),

    ("fed-051", "MADISON", "Federalist #51",
     ["separation-of-powers", "liberty", "faction", "government", "republic",
      "ambition", "federalism"],
     "Give each department the constitutional means and personal motives to resist "
     "encroachment by the others. Ambition must be made to counteract ambition. "
     "The interest of the man must be connected with the rights of the place. If "
     "men were angels, no government would be necessary. The compound republic "
     "adds a second safeguard: branches check branches, and state governments "
     "check federal. Within society, the multiplicity of interests prevents any "
     "one faction from dominating. Justice — protecting the rights of individuals "
     "and minorities — is the end government must secure."),

    ("fed-052", "MADISON", "Federalist #52",
     ["house", "elections", "representation", "people", "qualifications"],
     "Qualifications for House membership are minimal — age, citizenship, "
     "residency — leaving the widest possible field of eligible candidates. "
     "Biennial elections strike the right balance: frequent enough to maintain "
     "popular accountability, long enough for representatives to acquire knowledge "
     "of national affairs. Cited in cases about congressional qualifications "
     "including U.S. Term Limits v. Thornton (1995)."),

    ("fed-057", "MADISON", "Federalist #57",
     ["house", "elections", "suffrage", "people", "representation", "law"],
     "The House will not systematically favor the wealthy. Representatives must "
     "stand for election, are chosen by all qualified voters, and are bound by "
     "the laws they make — they cannot exempt themselves. The operative check "
     "against aristocratic capture is equal suffrage: every voter has the same "
     "weight. The structural argument that the House will represent ordinary "
     "citizens, not just the privileged."),

    ("fed-062", "MADISON", "Federalist #62",
     ["senate", "stability", "representation", "government", "faction"],
     "The Senate's smaller size, longer terms, and staggered elections provide "
     "legislative stability. A second chamber corrects hasty House legislation, "
     "maintains consistency in law, and prevents the evils that flow from "
     "mutable laws — damaged foreign confidence, economic uncertainty, and "
     "opportunities for insiders to profit from sudden legal changes."),

    ("fed-063", "MADISON", "Federalist #63",
     ["senate", "foreign", "stability", "representation", "continuity"],
     "The Senate provides institutional memory and continuity in foreign policy. "
     "No foreign nation will ratify treaties with a government that reverses "
     "positions every two years. The six-year term creates a body foreign nations "
     "can rely upon. Madison defends the Senate's deliberative character against "
     "the charge of aristocracy: it represents the people through election, but "
     "with enough distance from immediate passion to act wisely."),

    ("fed-064", "JAY", "Federalist #64",
     ["treaties", "senate", "executive", "foreign", "deliberation", "secrecy"],
     "The Senate and president together properly exercise the treaty power. "
     "Senators' six-year terms and small chamber size ensure the deliberation, "
     "secrecy, and knowledge of foreign affairs that a larger popular body cannot "
     "provide. The president adds executive dispatch and accountability. The men "
     "selected for the Senate and presidency will be the most distinguished in "
     "the nation — their combined judgment provides the best available guarantee "
     "against foolish or corrupt treaties."),

    ("fed-065", "HAMILTON", "Federalist #65",
     ["impeachment", "senate", "executive", "government", "law", "republic"],
     "The Senate is the proper court for impeachment trials. Impeachment concerns "
     "political offenses — abuse of public trust — that a regular jury is unfit "
     "to judge. A political body, held accountable by the people, must judge "
     "political crimes. The Chief Justice presides to ensure procedural dignity "
     "and to prevent the Vice President from presiding over a trial that "
     "determines his own succession. Criminal prosecution after acquittal remains "
     "available; double jeopardy does not bar it."),

    ("fed-066", "HAMILTON", "Federalist #66",
     ["impeachment", "senate", "executive", "separation-of-powers", "government"],
     "Answers specific objections to the Senate as impeachment court: the Senate "
     "will not simultaneously be judge and legislator in any meaningful sense — "
     "its judicial function in impeachment is entirely distinct from its "
     "legislative role. The President will not escape accountability through the "
     "Senate's foreign-affairs role; the two functions are separate. Hamilton "
     "systematically disposes of each procedural objection to the Senate trial."),

    ("fed-067", "HAMILTON", "Federalist #67",
     ["executive", "president", "power", "constitution", "government"],
     "Critics have wildly exaggerated the president's constitutional powers. "
     "Hamilton provides a precise inventory showing the executive is granted far "
     "less authority than opponents claim — and far less than a king. The "
     "vacancy-filling power for Senate seats, which critics attribute to the "
     "president, actually belongs to the states. Begins the systematic "
     "examination of executive powers running through #68–77."),

    ("fed-068", "HAMILTON", "Federalist #68",
     ["executive", "election", "people", "republic", "foreign-danger"],
     "The Electoral College selects the president through deliberative "
     "intermediaries — citizens chosen for judgment, insulated from popular "
     "passion and foreign intrigue. Electors meet separately in each state, "
     "preventing cabal. The body is temporary, created solely for the election, "
     "reducing corruption risk. No office more important to get right; no other "
     "feature more carefully designed."),

    ("fed-069", "HAMILTON", "Federalist #69",
     ["executive", "president", "king", "government", "power", "republic"],
     "The president's powers differ fundamentally from a monarch's: four-year "
     "limited term, no hereditary succession, suspensive rather than absolute "
     "veto, commander-in-chief subject to congressional control, no treaty power "
     "without Senate consent, no declaration of war. Systematic comparison to the "
     "British Crown and the New York governor shows the Constitution's executive "
     "is republican, not monarchical."),

    ("fed-070", "HAMILTON", "Federalist #70",
     ["executive", "energy", "unity", "government", "accountability"],
     "Energy in the executive is essential to good government: protection from "
     "foreign attack, steady law enforcement, security against faction and "
     "anarchy. Energy requires unity — one executive, not a council. Unity "
     "ensures decision, dispatch, and accountability. A council diffuses "
     "responsibility; a single executive can be watched and judged by the people. "
     "A plural executive, far from being safer, hides responsibility behind "
     "collective decision."),

    ("fed-071", "HAMILTON", "Federalist #71",
     ["executive", "independence", "government", "stability"],
     "Adequate duration in office gives the executive independence, the courage "
     "to act rightly, and the ability to pursue long-term plans rather than "
     "lame-duck passivity. An executive who knows his term is ending soon and "
     "cannot return has diminished incentive for excellence and may act "
     "desperately or recklessly."),

    ("fed-072", "HAMILTON", "Federalist #72",
     ["executive", "accountability", "government", "stability"],
     "Re-eligibility incentivizes good performance, allows retention of proven "
     "talent, and prevents the dangerous desperation of a president facing an "
     "imminent end to power with no prospect of extension."),

    ("fed-073", "HAMILTON", "Federalist #73",
     ["executive", "veto", "government", "independence", "legislature"],
     "Presidential salary must be constitutionally fixed — neither increased nor "
     "decreased during a term — to preserve independence from both Congress and "
     "the states. The qualified veto is defensive: the president can protect "
     "executive functions from legislative encroachment and prevent hasty "
     "legislation from becoming law. The two-thirds override requirement balances "
     "executive caution against majority legislative will. Cited in cases "
     "addressing the scope and limits of presidential veto power."),

    ("fed-074", "HAMILTON", "Federalist #74",
     ["executive", "pardons", "military", "government", "mercy"],
     "The president as commander-in-chief is appropriate: military command "
     "demands unity and decision that divided authority cannot provide. The pardon "
     "power properly rests in a single hand — a legislative pardon would invite "
     "political manipulation. In moments of rebellion, the executive's ability to "
     "extend clemency without conditions can restore order more effectively than "
     "continued prosecution."),

    ("fed-075", "HAMILTON", "Federalist #75",
     ["treaties", "executive", "senate", "foreign", "power", "government"],
     "Treaties are neither purely legislative nor purely executive — they are "
     "contracts between nations requiring executive secrecy and dispatch in "
     "negotiation, combined with the Senate's deliberative check on final "
     "consent. The two-thirds Senate requirement provides additional protection "
     "against hasty or corrupt agreements. Placing the full treaty power in the "
     "president alone would create unilateral executive authority over the most "
     "consequential national commitments."),

    ("fed-076", "HAMILTON", "Federalist #76",
     ["appointments", "executive", "senate", "government", "accountability"],
     "Presidential nomination with Senate confirmation is the best available "
     "mechanism for appointments. The president has incentive and superior "
     "information to nominate competent officers; the Senate can reject unfit "
     "nominees without bearing the burden of original selection. Congressional "
     "appointment invites logrolling and cabal; a single accountable executive's "
     "judgment is both more reliable and more transparent to the public."),

    ("fed-077", "HAMILTON", "Federalist #77",
     ["appointments", "executive", "senate", "government", "stability"],
     "Senate involvement in appointments promotes stability: the president cannot "
     "dismiss officers and replace them without Senate consent, preventing "
     "arbitrary and politically motivated turnover in the executive departments. "
     "Answers objections to the appointment process by showing that the Senate's "
     "role is purely confirmatory — initiative remains entirely with the "
     "president — while providing an institutional check against unfit nominees."),

    ("fed-078", "HAMILTON", "Federalist #78",
     ["judiciary", "constitution", "liberty", "law", "independence"],
     "The judiciary is the least dangerous branch: it holds neither sword nor "
     "purse, but only judgment. Its weakness requires independence, not restraint. "
     "Courts must have authority to void acts of Congress that contradict the "
     "Constitution — not because courts are superior to the legislature, but "
     "because the Constitution is the will of the people, which is superior to "
     "the will of their representatives. Lifetime tenure during good behavior is "
     "essential: without it, judges bend to whoever controls their continuation. "
     "Hamilton anticipates Marbury v. Madison by fifteen years."),

    ("fed-079", "HAMILTON", "Federalist #79",
     ["judiciary", "independence", "government"],
     "Judicial salaries must be undiminishable to preserve independence. "
     "Mandatory retirement at sixty-five is rejected as arbitrary; mental fitness "
     "varies too much by individual to admit of a fixed rule."),

    ("fed-080", "HAMILTON", "Federalist #80",
     ["judiciary", "federal", "jurisdiction", "law", "constitution", "states"],
     "Federal courts must have jurisdiction over all cases arising under the "
     "Constitution, federal statutes, and treaties; over controversies between "
     "states or citizens of different states; and over admiralty. Leaving federal "
     "questions to state courts would produce thirteen different interpretations "
     "of national law. Uniform judicial authority over the subjects of federal "
     "concern is essential to the meaning and enforceability of the Constitution."),

    ("fed-081", "HAMILTON", "Federalist #81",
     ["judiciary", "appellate", "constitution", "supreme-court", "law", "states"],
     "Congress may structure inferior federal courts as it sees fit. Supreme "
     "Court appellate review of state court decisions on federal questions is "
     "necessary to maintain uniform constitutional interpretation. Hamilton "
     "argues that suits by individuals against states without consent are not "
     "authorized by Article III — a position partially refuted by Chisholm v. "
     "Georgia (1793), which prompted the Eleventh Amendment."),

    ("fed-082", "HAMILTON", "Federalist #82",
     ["judiciary", "state-courts", "concurrent", "jurisdiction", "federal", "law"],
     "State courts may exercise concurrent jurisdiction over federal questions "
     "where Congress has not granted exclusive jurisdiction to federal courts. "
     "Practical necessity demands this: the federal judiciary cannot handle every "
     "case that touches federal law. State courts supplement federal capacity and, "
     "subject to Supreme Court review, provide an acceptable first-instance forum "
     "for many federal claims."),

    ("fed-083", "HAMILTON", "Federalist #83",
     ["judiciary", "jury-trial", "civil", "constitution", "law", "common-law"],
     "The Constitution does not abolish civil jury trial — it simply does not "
     "mandate it in all federal cases (as it does for criminal cases in Article "
     "III). The great diversity of state practices on civil juries made uniform "
     "constitutional specification impossible in 1787. Constitutional silence is "
     "not abolition; Congress retains authority to establish jury trial wherever "
     "it deems appropriate. Cited in Seventh Amendment civil jury cases."),

    ("fed-084", "HAMILTON", "Federalist #84",
     ["constitution", "liberty", "bill-of-rights", "press", "law"],
     "A bill of rights is unnecessary and potentially dangerous. The Constitution, "
     "as a grant of enumerated powers, is itself a bill of rights — only what is "
     "listed is granted. Enumerating rights creates a negative implication: rights "
     "not listed may be denied. Liberty of the press depends on public opinion and "
     "government character, not parchment declarations. Hamilton dismisses most "
     "remaining objections to the Constitution as answered by the document itself."),

    ("fed-085", "HAMILTON", "Federalist #85",
     ["ratification", "constitution", "amendment", "union", "republic", "liberty"],
     "Hamilton closes the series by urging immediate ratification of the imperfect "
     "Constitution, with amendments to follow through Article V. Perfection is "
     "impossible; the real choice is between this Constitution and the chaos of a "
     "dissolved Union. A second constitutional convention would produce greater "
     "disagreement, not greater wisdom. Accept a good constitution now rather than "
     "chase a perfect one that will never arrive."),

    # ================================================================
    # ANTI-FEDERALIST PAPERS — cited in SCOTUS opinions post-1981
    # (Zelinsky, Alabama Law Review, 2013; Garcia v. San Antonio, 1985;
    #  Heller, 2008; McDonald, 2010; Printz, 1997)
    # ================================================================

    ("af-brutus-01", "BRUTUS", "Anti-Fed: Brutus #1",
     ["constitution", "power", "states", "liberty", "military", "representation",
      "faction", "republic"],
     "The most powerful Anti-Federalist argument. The supremacy clause combined "
     "with the necessary and proper clause grants virtually unlimited power to "
     "Congress: whatever it deems necessary for enumerated ends becomes supreme "
     "law binding on the states. The taxing power, with no named limit, will "
     "expand until federal revenue crowds out the states entirely. A standing army "
     "has historically been the instrument of tyranny; free states rely on citizen "
     "militias. Representation is fatally thin: sixty-five representatives cannot "
     "know the interests of three million people across a continent. Only a small "
     "republic can maintain the civic virtue republican government requires. "
     "Attributed to Robert Yates of New York."),

    ("af-brutus-06", "BRUTUS", "Anti-Fed: Brutus #6",
     ["judiciary", "power", "federal", "states", "constitution", "expansion"],
     "Federal courts will gradually enlarge their jurisdiction and give broad "
     "construction to every federal power. The distinction between cases arising "
     "under federal law and common-law cases will erode until federal courts "
     "exercise effectively general jurisdiction. State courts will be subordinated "
     "to federal review on virtually every question touching national law. Unlike "
     "legislative overreach, judicial overreach cannot be corrected at the ballot "
     "box. Brutus's prediction proved prescient for federal judicial expansion."),

    ("af-brutus-11", "BRUTUS", "Anti-Fed: Brutus #11",
     ["judiciary", "power", "constitution", "liberty", "supremacy", "law"],
     "The Supreme Court is more dangerous than any other branch because its "
     "decisions are final and unreviewable. Judges will give the most liberal "
     "construction to congressional powers, and their interpretations will harden "
     "into binding precedent impossible to reverse. Unlike Britain, where "
     "Parliament can override court decisions, the proposed Constitution provides "
     "no mechanism to check judicial overreach. This essay is the Anti-Federalist "
     "paper most frequently cited in modern SCOTUS opinions — often invoked "
     "against judicial supremacy by justices across the ideological spectrum."),

    ("af-brutus-12", "BRUTUS", "Anti-Fed: Brutus #12",
     ["judiciary", "power", "constitution", "accountability", "liberty"],
     "Judges holding office during good behavior, with fixed salaries and no "
     "political accountability, will become a law unto themselves. The power to "
     "void legislative acts makes the court superior to Congress, yet the court "
     "itself faces no equivalent check. The remedy — impeachment — is impractical "
     "for judicial overreach on constitutional questions. Cited in cases and "
     "scholarship on the countermajoritarian difficulty and judicial "
     "accountability."),

    ("af-brutus-15", "BRUTUS", "Anti-Fed: Brutus #15",
     ["judiciary", "jurisdiction", "states", "federal", "power", "constitution"],
     "Federal courts will eventually absorb all state judicial functions through "
     "expansion of the Article III 'arising under' jurisdiction. The practical "
     "scope of federal jurisdiction has no natural stopping point: any case "
     "touching a federal statute or constitutional right can be characterized as "
     "arising under federal law. State courts will be reduced to administrative "
     "tribunals reviewing purely local matters. Cited in debates over the scope "
     "of Article III and federal question jurisdiction."),

    ("af-federal-farmer-01", "FEDERAL_FARMER", "Anti-Fed: Federal Farmer #1",
     ["constitution", "union", "states", "representation", "deliberation"],
     "The choice is not between this Constitution and anarchy — genuine reform of "
     "the Articles was possible without replacement. The Federal Farmer urges "
     "deliberation over urgency: the Convention exceeded its mandate by proposing "
     "a new frame rather than amendments. Consolidation of power, once achieved, "
     "is difficult to reverse. A true federal system requires stronger state "
     "representation and a genuine balance between levels of government. Attributed "
     "to Richard Henry Lee or Melancton Smith."),

    ("af-federal-farmer-02", "FEDERAL_FARMER", "Anti-Fed: Federal Farmer #2",
     ["representation", "people", "senate", "liberty", "government"],
     "Representatives must be numerous enough to actually know the people's varied "
     "interests. Few representatives, long terms, and geographic distance ensure "
     "that only the wealthy and well-connected can effectively serve — producing "
     "an aristocracy in republican dress."),

    ("af-federal-farmer-06", "FEDERAL_FARMER", "Anti-Fed: Federal Farmer #6",
     ["bill-of-rights", "liberty", "constitution", "rights", "government"],
     "A bill of rights is not merely desirable but essential. The standard "
     "Federalist response — enumerated powers mean unenumerated rights are safe — "
     "is historically insufficient: governments routinely expand beyond their "
     "grants. A bill of rights provides a textual anchor for liberties that would "
     "otherwise face gradual erosion. The Federal Farmer directly rebuts Hamilton's "
     "Federalist #84 argument and is among the Anti-Federalist writings credited "
     "with forcing the addition of the first ten amendments."),

    ("af-centinel-01", "CENTINEL", "Anti-Fed: Centinel #1",
     ["government", "liberty", "people", "power", "constitution", "representation"],
     "Pennsylvania's minority dissent. The proposed Constitution shifts power to "
     "a distant, aristocratic central government accountable to no one. A single "
     "accountable legislature is superior to bicameralism, which insulates "
     "aristocratic senators from popular pressure. The Convention operated in "
     "secrecy; its product was rushed to ratification without adequate public "
     "debate. Haste benefits those who profit from confusion. Attributed to "
     "Samuel Bryan."),

    ("af-cato-03", "CATO", "Anti-Fed: Cato #3",
     ["republic", "virtue", "democracy", "representation", "people"],
     "An extended republic destroys civic virtue. Ancient republics were small "
     "for good reason: representation cannot substitute for direct participation; "
     "distance breeds corruption and indifference to the public good. Attributed "
     "to George Clinton, Governor of New York."),

    ("af-cato-05", "CATO", "Anti-Fed: Cato #5",
     ["executive", "power", "reeligibility", "patronage", "republic", "liberty"],
     "An executive eligible for re-election will use the powers of office to "
     "secure his own continuation — distributing patronage, expanding the "
     "military, and cultivating popular favor at public expense. The Roman example "
     "shows that executive re-eligibility leads to perpetual occupancy and "
     "eventually tyranny. Directly contradicts Hamilton's Federalist #72 defense "
     "of re-eligibility. Cited in cases and scholarship on executive term limits "
     "and the Twenty-Second Amendment."),
]


# ---------------------------------------------------------------------------
# Optional: enrich with first sentence of actual paper text if available.
# ---------------------------------------------------------------------------
def load_raw() -> dict[int, str]:
    if not RAW.exists():
        return {}
    try:
        papers = json.loads(RAW.read_text(encoding="utf-8"))
        out = {}
        for p in papers:
            text = p.get("text", "")
            m    = re.search(r"([A-Z][^.!?]+[.!?])", text)
            if m:
                out[p["number"]] = m.group(1).strip()
        return out
    except Exception:
        return {}


def slugify(text: str, max_words: int = 5) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    skip  = {"the","a","an","of","to","and","is","it","that","this","in","on",
             "but","with","or","not","by","for","if","as","be","are","do","you",
             "from","its","their","which","have","has","at","was","will","been"}
    keep  = [w for w in words if w not in skip][:max_words]
    return "-".join(keep) if keep else "note"


def main():
    NOTES.mkdir(parents=True, exist_ok=True)
    for pat in ("fed-*.md", "af-*.md", "ref-*.md"):
        for f in NOTES.glob(pat): f.unlink()

    raw_texts = load_raw()

    for note_id, speaker, source, tags, body in NOTES_DATA:
        m = re.match(r"fed-0*(\d+)$", note_id)
        if m and int(m.group(1)) in raw_texts:
            lead = raw_texts[int(m.group(1))]
            if lead not in body:
                body = f'[Opening: "{lead}"]\n\n{body}'

        slug  = slugify(body)
        fname = f"{note_id}-{speaker.lower()}-{slug}.md"
        wc    = len(body.split())
        fm    = (
            f"---\n"
            f"id: {note_id}\n"
            f"speaker: {speaker}\n"
            f'source: "{source}"\n'
            f"tags: [{', '.join(tags)}]\n"
            f"word_count: {wc}\n"
            f"---\n\n"
            f"{body}\n"
        )
        (NOTES / fname).write_text(fm, encoding="utf-8")

    fed_count = sum(1 for n in NOTES_DATA if n[0].startswith("fed"))
    af_count  = sum(1 for n in NOTES_DATA if n[0].startswith("af"))
    print(f"Wrote {len(NOTES_DATA)} notes to {NOTES}")
    print(f"  Federalist:      {fed_count}")
    print(f"  Anti-Federalist: {af_count}")
    by_spk = {}
    for n in NOTES_DATA:
        by_spk[n[1]] = by_spk.get(n[1], 0) + 1
    for spk, cnt in sorted(by_spk.items()):
        print(f"  {spk:16s} {cnt:2d} notes")
    if raw_texts:
        print(f"  Enriched with real text for {len(raw_texts)} Federalist papers")


if __name__ == "__main__":
    main()
