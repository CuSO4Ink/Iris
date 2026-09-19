using System;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Xml.Linq;
using System.Runtime.CompilerServices;
using System.Text.RegularExpressions;
using Verse;
using RimWorld;
using Defaults;
using Defaults.StockpileZones;
using Defaults.StockpileZones.Buildings;
using Defaults.WorkbenchBills;
namespace IrisStorageDefaults {
public class StorageMod : Mod { public static string Root; public StorageMod(ModContentPack pack):base(pack){Root=pack.RootDir;} }
public static class Rules {
 public static readonly HashSet<ThingDef> Banned=new HashSet<ThingDef>();
 static readonly Regex BadMeat=new Regex(@"human|ratkin|kiiro|milira|alien_|axolotl$|dragonian|smeltedloong|vv_vivi|mugirl|wolfein|necronoid|necro_|rh_df|corpsecreature|evilcreature|crimsontyrant|twisted|rottenegg|maggot|megaspider|xxk_(flukemunga|huskhive|hwurmp)|bendan_rkpsycast_(mawile|nunrat)|insectgirl",RegexOptions.IgnoreCase);
 static readonly Regex Reserve=new Regex(@"resurrect|reviv|serum|nanite|hemogen|cure|curing|medicine|elixir|drug|soul|blood|specialraid|summon|fertiliz|tear|lucifer|ambrosia",RegexOptions.IgnoreCase);
 static bool InCategory(ThingCategoryDef c,string name){for(var p=c;p!=null;p=p.parent)if(p.defName.Equals(name,StringComparison.OrdinalIgnoreCase))return true;return false;}
 public static bool Cat(ThingDef d,string cat){return d.thingCategories!=null && d.thingCategories.Any(c=>InCategory(c,cat));}
 public static bool Food(ThingDef d){return !d.IsCorpse && d.ingestible!=null && d.ingestible.foodType!=FoodTypeFlags.None;}
 public static bool ForbiddenMeat(string name,bool humanlike,bool insect){return humanlike||insect||BadMeat.IsMatch(name);}
 public static bool Meat(ThingDef d){return d.IsMeat || d.defName.StartsWith("Meat_") || Cat(d,"MeatRaw");}
 public static bool Fertile(ThingDef d){return d.HasComp(typeof(CompHatcher))||Regex.IsMatch(d.defName.Replace("Unfertilized","Unfertile"),"fertiliz",RegexOptions.IgnoreCase);}
 public static bool Special(ThingDef d){return Fertile(d)|| d.IsDrug || Cat(d,"Medicine") || Reserve.IsMatch(d.defName.Replace("Unfertilized","Unfertile"));}
 public static bool Raw(ThingDef d){return Food(d)&&!Banned.Contains(d)&&!Special(d)&& (Cat(d,"FoodRaw") || Cat(d,"FoodsRaw") || (d.ingestible.foodType & (FoodTypeFlags.Meat|FoodTypeFlags.VegetableOrFruit|FoodTypeFlags.AnimalProduct))!=0) && (d.ingestible.foodType & (FoodTypeFlags.Meal|FoodTypeFlags.Processed))==0;}
 public static bool Meal(ThingDef d){return Food(d)&&!Banned.Contains(d)&&!Special(d)&&!Raw(d)&&d.ingestible.HumanEdible&&d.ingestible.preferability>=FoodPreferability.RawTasty&&d.defName!="BabyFood";}
 public static bool Matches(string role,ThingDef d){
  if(role=="animalcorpse")return d.IsCorpse && d.ingestible?.sourceDef?.race?.Animal==true && !BadMeat.IsMatch(d.defName);
  if(role=="bio")return Food(d);
  if(Banned.Contains(d)||d.IsCorpse)return false;
  switch(role){
   case "baby":return d.defName=="BabyFood";
   case "eggs":return Fertile(d);
   case "reserved":return d.category==ThingCategory.Item&&Special(d)&&(d.ingestible!=null||d.IsDrug)&&!Fertile(d);
   case "coded":return d.IsWeapon||d.IsApparel;
   case "laundry":return d.IsApparel;
   case "raw":return Raw(d);
   case "meal":return Meal(d);
   case "weapon":return d.IsWeapon;
   case "apparel":return d.IsApparel;
   case "book":return Cat(d,"Books") || d.HasComp(typeof(CompBook));
   case "textile":return Cat(d,"Textiles")||Cat(d,"Leathers")||Cat(d,"Wools") || d.stuffProps?.categories?.Any(c=>c.defName=="Fabric")==true;
   case "valuable":return d.defName=="Silver"||d.defName=="Gold"||d.defName=="Jade";
   case "medical":return Cat(d,"Medicine")||d.defName=="HemogenPack" || (d.category==ThingCategory.Item && Regex.IsMatch(d.defName,"resurrect|reviv|healer|medicine",RegexOptions.IgnoreCase));
   case "fuel":return d.defName=="Chemfuel";
   case "bulk":return d.defName=="Steel"||d.defName=="Plasteel"||d.defName=="WoodLog"||d.defName=="Uranium"||d.defName=="Bioferrite"||(!Matches("valuable",d)&&!Food(d)&&!Cat(d,"Chunks")&&(Cat(d,"StoneBlocks")||(Cat(d,"ResourcesRaw")&&d.stuffProps!=null&&!Matches("textile",d))));
   case "precision":return d.category==ThingCategory.Item&&!Food(d)&&!d.IsDrug&&!Matches("medical",d)&&!Matches("bulk",d)&&!Matches("valuable",d)&&!Cat(d,"MortarShells")&&d.defName!="Chemfuel" && (Cat(d,"Manufactured")||Regex.IsMatch(d.defName,"component|chip|core|psycaststone|gravlite",RegexOptions.IgnoreCase));
   case "generic":case "fallback":return d.EverHaulable&&d.category==ThingCategory.Item&&!Food(d)&&!Cat(d,"Chunks")&&d.defName!="Wastepack";
  }return false;
 }
 public static void Build(List<ThingDef> defs){
  Banned.Clear();
  foreach(var d in defs) {
   var race=d.ingestible?.sourceDef?.race;
   if(Meat(d) && ForbiddenMeat(d.defName,race?.Humanlike==true,race?.Insect==true||race?.IsAnomalyEntity==true))Banned.Add(d);
   if(Food(d)&&Regex.IsMatch(d.defName,"necronoid|necro_|humanSurimi|corpsecreature|evilcreature",RegexOptions.IgnoreCase))Banned.Add(d);
  }
  foreach(var d in defs.Where(d=>d.race!=null)) {
   string pid=d.modContentPack?.PackageIdPlayerFacing??"";
   bool forbidden=d.race.Humanlike||d.race.Insect||d.race.IsAnomalyEntity||Regex.IsMatch(d.defName+" "+pid,"necronoid|insectgirl|zal.taofc|rh_df|corpsecreature|evilcreature|crimsontyrant",RegexOptions.IgnoreCase);
   if(!forbidden)continue;
   RegisterMeatProduct(d.race.meatDef);
   if(d.butcherProducts!=null)foreach(var p in d.butcherProducts)if(Meat(p.thingDef))Banned.Add(p.thingDef);
  }
 }
 public static void RegisterMeatProduct(ThingDef d){if(d!=null&&Meat(d))Banned.Add(d);}
 public static void Exclude(ThingFilter f,params string[] names){foreach(string n in names){var d=DefDatabase<SpecialThingFilterDef>.GetNamedSilentFail(n);if(d!=null)f.SetAllow(d,false);}}
 public static bool ForbiddenIngredients(ThingDef item,IEnumerable<ThingDef> ingredients){return Banned.Contains(item)||(ingredients!=null&&ingredients.Any(d=>Banned.Contains(d)));}
 public static void FoodGuard(ThingFilter f){foreach(var d in Banned)f.SetAllow(d,false);Exclude(f,"AllowCannibal","AllowInsectMeat","AllowRotten","Iris_ForbiddenFoodSources");}
 public static StoragePriority Priority(string r){return r=="generic"?StoragePriority.Preferred:r=="fallback"?StoragePriority.Low:r=="bio"?StoragePriority.Normal:(r=="weapon"||r=="meal"||r=="medical")?StoragePriority.Critical:StoragePriority.Important;}
}
public class ForbiddenSourceFilter : SpecialThingFilterWorker {
 public override bool Matches(Thing t){var c=t.TryGetComp<CompIngredients>();return Rules.ForbiddenIngredients(t.def,c?.ingredients);}
 public override bool CanEverMatch(ThingDef d){return Rules.Food(d)||d.HasComp(typeof(CompIngredients));}
}
public class CleanFoodSourceFilter : SpecialThingFilterWorker {
 public override bool Matches(Thing t){var c=t.TryGetComp<CompIngredients>();return !Rules.ForbiddenIngredients(t.def,c?.ingredients);}
 public override bool CanEverMatch(ThingDef d){return Rules.Food(d)||d.HasComp(typeof(CompIngredients));}
}
[StaticConstructorOnStartup] public static class Startup {
 static Startup(){try{RuntimeHelpers.RunClassConstructor(typeof(DefaultsModInitializer).TypeHandle);Apply();}catch(Exception e){Verse.Log.Error("[Iris Storage Defaults] Templates update failed: "+e);}}
 static void Fill(ZoneType z,string role,List<ThingDef> defs,ThingDef building=null){
  z.filter.SetDisallowAll();foreach(var d in defs)if(Rules.Matches(role,d)&&(building?.building?.fixedStorageSettings==null||building.building.fixedStorageSettings.filter.Allows(d)))z.filter.SetAllow(d,true);
  z.priority=Rules.Priority(role);z.locked=true;
  if(role=="bio")Rules.Exclude(z.filter,"Iris_CleanFoodSources");else Rules.FoodGuard(z.filter);
  if(role=="coded")Rules.Exclude(z.filter,"AllowNonBiocodedWeapons","AllowNonBiocodedApparel");
  if(role=="laundry")Rules.Exclude(z.filter,"AllowNonDeadmansApparel");
  if(role=="weapon")Rules.Exclude(z.filter,"AllowBiocodedWeapons");
  if(role=="generic")Rules.Exclude(z.filter,"AllowBiocodedWeapons");
  if(role=="apparel"||role=="generic")Rules.Exclude(z.filter,"AllowDeadmansApparel","AllowBiocodedApparel");
 }
 static void Apply(){
  var defs=DefDatabase<ThingDef>.AllDefsListForReading;Rules.Build(defs);
  var manifest=XDocument.Load(Path.Combine(StorageMod.Root,"StorageRules.xml"));
  var buildings=Settings.Get<Dictionary<ThingDef,ZoneType_Building>>(Settings.BUILDING_STORAGE);
  var zones=Settings.Get<List<ZoneType>>(Settings.STOCKPILE_ZONES);
  int count=0;
  foreach(var n in manifest.Root.Element("buildings").Elements("li")){
   var d=DefDatabase<ThingDef>.GetNamedSilentFail((string)n.Attribute("def"));
   if(d!=null&&buildings.TryGetValue(d,out var z)){Fill(z,(string)n.Attribute("role"),defs,d);count++;}
  }
  foreach(var n in manifest.Root.Element("zones").Elements("li")){
   string name=(string)n.Attribute("name");var z=zones.FirstOrDefault(x=>x.Name==name);if(z==null){z=new ZoneType(name,StorageSettingsPreset.DefaultStockpile);zones.Add(z);}Fill(z,(string)n.Attribute("role"),defs);
  }
  foreach(var pair in buildings){
   if(!new[]{"Hopper","BiosculpterPod","GrowthVat","SR_GenePurifierPod","WRMC_WolfeinGrowthVat"}.Contains(pair.Key.defName))continue;
   Rules.FoodGuard(pair.Value.filter);
   foreach(var d in defs)if(Rules.Special(d))pair.Value.filter.SetAllow(d,false);
   pair.Value.locked=true;
  }
  foreach(var p in Settings.Get<List<FoodPolicy>>(Settings.POLICIES_FOOD)){
   if(p.label=="正食配置")foreach(var d in defs)if(Rules.Meal(d))p.filter.SetAllow(d,true);
   Rules.FoodGuard(p.filter);
  }
  foreach(var group in Settings.Get<List<WorkbenchBillStore>>(Settings.WORKBENCH_BILLS))foreach(var b in group.bills){
   if(b.recipe==null || !(b.recipe.defName.StartsWith("Cook")||b.recipe.defName.StartsWith("Make_Pemmican")||b.recipe.products?.Any(p=>Rules.Meal(p.thingDef))==true))continue;
   foreach(var d in defs) {
    if(Rules.Special(d)&&Rules.Food(d))b.ingredientFilter.SetAllow(d,false);
    else if(Rules.Raw(d)&&b.recipe.fixedIngredientFilter.Allows(d))b.ingredientFilter.SetAllow(d,true);
   }
   Rules.FoodGuard(b.ingredientFilter);b.locked=true;
  }
  DefaultsMod.SaveSettings(false);
  Verse.Log.Message("[Iris Storage Defaults] Updated "+count+" storage templates; blocked "+Rules.Banned.Count+" food sources. Existing map storage and pawn policies unchanged.");
 }
}
}
