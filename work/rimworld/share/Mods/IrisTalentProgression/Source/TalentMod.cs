using System;
using System.Linq;
using HarmonyLib;
using RimWorld;
using UnityEngine;
using Verse;
using VSE.Passions;
namespace IrisTalentProgression {
 public sealed class TalentSettings : ModSettings {
  public bool Enabled=true, PreserveCombat=true;
  public float Scale=1f, SpecialistChance=0.30f, DevelopmentStrength=1f;
  public string ExcludedKinds="";
  public override void ExposeData(){Scribe_Values.Look(ref Enabled,"enabled",true);Scribe_Values.Look(ref PreserveCombat,"preserveCombat",true);Scribe_Values.Look(ref Scale,"scale",1f);Scribe_Values.Look(ref SpecialistChance,"specialistChance",0.30f);Scribe_Values.Look(ref DevelopmentStrength,"developmentStrength",1f);Scribe_Values.Look(ref ExcludedKinds,"excludedKinds","");}
 }
 public sealed class TalentMod : Mod {
  internal static TalentSettings Settings;
  public TalentMod(ModContentPack c):base(c){Settings=GetSettings<TalentSettings>();new Harmony("local.iristalentprogression").Patch(AccessTools.Method(typeof(PawnGenerator),"GenerateSkills"),postfix:new HarmonyMethod(typeof(TalentMod),nameof(AfterSkills)){priority=Priority.Last});Log.Message("[IrisTalentProgression] New-adult skill shaping installed; existing pawns untouched.");}
  public override string SettingsCategory()=>"Iris 人才成长";
  public override void DoSettingsWindowContents(Rect rect){var l=new Listing_Standard();l.Begin(rect);l.Label("只影响之后新生成的成年人；已有角色与学习速度不变。");l.CheckboxLabeled("启用人才分布",ref Settings.Enabled);l.CheckboxLabeled("保留非玩家战斗职业的射击/格斗与对应热情",ref Settings.PreserveCombat);l.Label("新人等级强度："+Settings.Scale.ToString("F2"));Settings.Scale=l.Slider(Settings.Scale,0.5f,1.5f);l.Label("专才比例："+Settings.SpecialistChance.ToString("P0"));Settings.SpecialistChance=l.Slider(Settings.SpecialistChance,0f,0.65f);l.Label("发展对人才的影响："+Settings.DevelopmentStrength.ToString("F2"));Settings.DevelopmentStrength=l.Slider(Settings.DevelopmentStrength,0f,1f);l.Label("额外排除的 PawnKind defName（逗号分隔）");Settings.ExcludedKinds=l.TextEntry(Settings.ExcludedKinds);l.Label("领袖、贵族、特殊加入者、未成年人和开局人物自动排除。修改立即影响后续生成。");l.End();}
  internal static bool HasDeclaredSkillGain(Pawn pawn, SkillDef skill) {
   if (pawn.story == null) return false;
   return pawn.story.AllBackstories.Any(b => b?.skillGains?.Any(g => g.skill == skill && g.amount != 0) == true)
    || pawn.story.traits?.allTraits.Any(t => !t.Suppressed && t.CurrentData.skillGains?.Any(g => g.skill == skill && g.amount != 0) == true) == true;
  }
  internal static bool HasKindSkillRule(PawnKindDef kind,SkillDef skill) => kind.extraSkillLevels!=0 || kind.skills?.Any(r=>r.Skill==skill)==true;
  static void AfterSkills(Pawn pawn,PawnGenerationRequest request){
   if(!Settings.Enabled || pawn?.skills==null || !pawn.RaceProps.Humanlike || pawn.DevelopmentalStage!=DevelopmentalStage.Adult || request.Context.ToString()=="PlayerStarter" || request.KindDef.factionLeader || request.FixedTitle!=null || request.IsCreepJoiner)return;
   if(pawn.kindDef.minTotalSkillLevels>0 || pawn.kindDef.minBestSkillLevel>0 || pawn.kindDef.extraSkillLevels!=0)return;
   if(Settings.ExcludedKinds.Split(',').Any(x=>x.Trim()==pawn.kindDef.defName))return;
   var skills=pawn.skills.skills.Where(x=>!x.TotallyDisabled && !HasDeclaredSkillGain(pawn,x.def) && !HasKindSkillRule(pawn.kindDef,x.def)).ToArray();if(skills.Length<2)return;
   var levels=skills.Select(x=>x.Level).ToArray();var passions=skills.Select(x=>x.passion).ToArray();
   double progress=Current.Game?.GetComponent<TalentDevelopment>()?.Value??0;
   var result=TalentPolicy.Generate(levels.Select(x=>(double)x).ToArray(),progress*Math.Max(0,Math.Min(1,Settings.DevelopmentStrength)),Math.Max(0.5,Math.Min(1.5,Settings.Scale)),Math.Max(0,Math.Min(0.65,Settings.SpecialistChance)),new System.Random(Rand.Range(1,int.MaxValue)));
   string[] names={"None","Minor","Major","VSE_Apathy","VSE_Natural","VSE_Critical"};
   for(int i=0;i<skills.Length;i++){
    var s=skills[i];
    if(Settings.PreserveCombat && pawn.kindDef.isFighter && pawn.Faction?.IsPlayer!=true && (s.def==SkillDefOf.Shooting || s.def==SkillDefOf.Melee))continue;
    s.Level=result.Levels[i];s.xpSinceLastLevel=0;
    bool required=pawn.story?.traits?.allTraits.Any(t=>!t.Suppressed && t.def.RequiresPassion(s.def))==true;
    bool forbidden=pawn.story?.traits?.allTraits.Any(t=>!t.Suppressed && t.def.ConflictsWithPassion(s.def))==true;
    bool geneLocked=pawn.genes?.GenesListForReading.Any(g=>g.Active && g.def.passionMod!=null && g.def.passionMod.skill==s.def)==true;
    if(!required && !geneLocked)s.passion=forbidden?Passion.None:(Passion)DefDatabase<PassionDef>.GetNamed(names[result.Passions[i]]).index;
   }
   LearnRateFactorCache.ClearCache();
  }
 }
 public sealed class TalentDevelopment : GameComponent {
  float value=-1f;int lastUpdate=-1;
  public TalentDevelopment(Game game){}
  public float Value {get{Update();return Math.Max(0,value);}}
  public override void ExposeData(){Scribe_Values.Look(ref value,"development",-1f);Scribe_Values.Look(ref lastUpdate,"lastUpdate",-1);}
  public override void GameComponentTick(){if(Find.TickManager.TicksGame%2500==0)Update();}
  void Update(){
   int now=Find.TickManager?.TicksGame??0;
   if(value>=0 && now-lastUpdate<2500)return;
   var maps=Find.Maps?.Where(m=>m.IsPlayerHome).ToArray();
   if(maps==null || maps.Length==0)return;
   double days=now/60000.0;
   double research=DefDatabase<ResearchProjectDef>.AllDefs.Where(r=>r.IsFinished).Sum(r=>(double)Math.Max(0,r.baseCost));
   double buildings=maps.Sum(m=>(double)Math.Max(0,m.wealthWatcher.WealthBuildings));
   float target=(float)(0.2*Math.Min(1,days/180)+0.45*Math.Min(1,research/60000)+0.35*Math.Min(1,buildings/150000));
   if(value<0)value=target;else value+=(target-value)*(float)(1-Math.Exp(-Math.Max(0,now-lastUpdate)/180000.0));
   lastUpdate=now;
  }
 }
}

