//
//  RankingsMenuData.swift
//  Pro Billards Software
//
//  Drill-down menu matching web app: top → category → ranking list.
//

import Foundation

/// One level of drill: either a submenu (more items) or a leaf (ranking system to load).
enum RankingsMenuItem {
    case drill(id: String, label: String, style: MenuStyle)
    case leaf(system: String, label: String, style: MenuStyle)
}

enum MenuStyle {
    case wpba
    case wpa
    case heyball
}

/// Top-level categories (matches web TOP_LEVEL_ITEMS).
let rankingsTopLevel: [RankingsMenuItem] = [
    .drill(id: "wpba", label: "👑 WPBA", style: .wpba),
    .drill(id: "wpa", label: "🌍 WPA", style: .wpa),
    .drill(id: "heyball", label: "🎯 Heyball", style: .heyball),
    .drill(id: "wpa_artistic", label: "🎨 Artistic Pool", style: .wpa),
]

/// Submenus per drill id (matches web DRILL_MENUS).
func rankingsMenuItems(for drillId: String) -> [RankingsMenuItem] {
    switch drillId {
    case "wpba":
        return [
            .leaf(system: "WPBA_Women", label: "👑 WPBA Women (overall)", style: .wpba),
            .leaf(system: "WPBA_Women_IronCityVI", label: "🏆 Iron City Invitational VI 2025", style: .wpba),
            .leaf(system: "WPBA_Women_DRPool2025", label: "🏆 DR Pool Championship 2025", style: .wpba),
            .leaf(system: "WPBA_Women_RaxxMezz2025", label: "🏆 Raxx Mezz Invitational 2025", style: .wpba),
            .leaf(system: "WPBA_Women_SoaringEagle2025", label: "🏆 Soaring Eagle Invitational 2025", style: .wpba),
            .leaf(system: "WPBA_Women_Colorado2025", label: "🏆 Colorado Classic 2025", style: .wpba),
            .leaf(system: "WPBA_Women_Jacoby2025", label: "🏆 Jacoby Tour Masters 2025", style: .wpba),
            .leaf(system: "WPBA_Women_Jacoby2024", label: "🏆 Jacoby Tour Championship 2024", style: .wpba),
            .leaf(system: "WPBA_Women_Colorado2024", label: "🏆 Colorado Classic 2024", style: .wpba),
            .leaf(system: "WPBA_Women_NAPA2024", label: "🏆 Cuespeed NAPA Invitational 2024", style: .wpba),
            .leaf(system: "WPBA_Women_CapitalCity2024", label: "🏆 Capital City Invitational 2024", style: .wpba),
            .leaf(system: "WPBA_Women_Palmetto", label: "🏆 Palmetto Billiards Invitational 2024", style: .wpba),
        ]
    case "wpa":
        return [
            .drill(id: "wpa_women", label: "🌍 WPA Women", style: .wpa),
            .drill(id: "wpa_men", label: "🎱 WPA Men", style: .wpa),
        ]
    case "wpa_women":
        return [
            .leaf(system: "WPA_Women", label: "🌍 WPA Women (overall)", style: .wpa),
            .leaf(system: "WPA_Women_9B_WorldChamp", label: "🎱 WPA 9-Ball World Championship 2025", style: .wpa),
            .leaf(system: "WPA_Women_LittleMonster", label: "🎱 Little Monster International Open 2025", style: .wpa),
            .leaf(system: "WPA_Women_AllJapan57", label: "🎱 57th All Japan Championship 2025", style: .wpa),
            .leaf(system: "WPA_Women_DRPoolTour", label: "🎱 WPBA DR Pool Tour Championship 2025", style: .wpa),
            .leaf(system: "WPA_Women_10B_Predator", label: "🎱 Predator 10-Ball World Championship 2025", style: .wpa),
            .leaf(system: "WPA_Women_9Ball", label: "🎱 Poison Saigon 9-Ball Open 2025", style: .wpa),
            .leaf(system: "WPA_Women_JapanOpen", label: "🎱 Japan Open 2025", style: .wpa),
            .leaf(system: "WPA_Women_ChinaOpen", label: "🎱 China Open 2025", style: .wpa),
            .leaf(system: "WPA_Women_WPBA_Colorado", label: "🎱 WPBA Olhausen Colorado Classic 2025", style: .wpa),
            .leaf(system: "WPA_Women_10B_Indonesia", label: "🎱 Indonesia 10-Ball Open 2025", style: .wpa),
            .leaf(system: "WPA_Women_8Ball", label: "🎱 WPA 8-Ball World Championship 2025", style: .wpa),
            .leaf(system: "WPA_Women_WPBA_SEMasters", label: "🎱 WPBA SE Masters 2025", style: .wpa),
            .leaf(system: "WPA_Women_WPBA_RaxxMezz", label: "🎱 WPBA Raxx Mezz 2025", style: .wpa),
            .leaf(system: "WPA_Women_Kamui_LasVegas", label: "🎱 Kamui Las Vegas Open 2025", style: .wpa),
            .leaf(system: "WPA_Women_WPBA_IronCity", label: "🎱 WPBA Olhausen IronCity 2025", style: .wpa),
        ]
    case "wpa_men":
        return [
            .leaf(system: "WPA_Men", label: "🎱 WPA Men (overall)", style: .wpa),
            .leaf(system: "WPA_Men_10B_Polish", label: "🎱 Jax Men's International Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_Maldives", label: "🎱 Little Monster International Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_HCM", label: "🎱 58th All Japan Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_9B_IntlOpen", label: "🎱 International 9-Ball Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_10B_Qatar", label: "🎱 Qatar World Cup 10-Ball 2025", style: .wpa),
            .leaf(system: "WPA_Men_Yalin_8Ball", label: "🎱 Yalin 8-Ball World Championship 2025", style: .wpa),
            .leaf(system: "WPA_Men_Predator_10B", label: "🎱 Predator 10-Ball World Championship 2025", style: .wpa),
            .leaf(system: "WPA_Men_JPBA_JapanOpen", label: "🎱 38th JPBA Japan Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_9B_ChinaOpen", label: "🎱 Pudong 9-Ball China Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_9B_WorldChamp", label: "🎱 9-Ball World Championship 2025", style: .wpa),
            .leaf(system: "WPA_Men_10B_Indonesia", label: "🎱 Indonesia 10-Ball Open 2025", style: .wpa),
            .leaf(system: "WPA_Men_Kamui_LasVegas", label: "🎱 Kamui Las Vegas Open 2025", style: .wpa),
        ]
    case "wpa_artistic":
        return [
            .leaf(system: "WPA_Artistic", label: "🎨 Artistic Pool (overall)", style: .wpa),
            .leaf(system: "WPA_Artistic_2023_SAO", label: "🎨 2023 South African Open", style: .wpa),
            .leaf(system: "WPA_Artistic_2023_MC", label: "🎨 2023 Masters Championship", style: .wpa),
            .leaf(system: "WPA_Artistic_2022_WC", label: "🎨 2022 World Championship", style: .wpa),
            .leaf(system: "WPA_Artistic_2022_NC", label: "🎨 2022 National Championship", style: .wpa),
            .leaf(system: "WPA_Artistic_2021_NC", label: "🎨 2021 National Championship", style: .wpa),
            .leaf(system: "WPA_Artistic_2019_WC", label: "🎨 2019 World Championship", style: .wpa),
            .leaf(system: "WPA_Artistic_2019_CAO", label: "🎨 2019 Coughlin Auto Open", style: .wpa),
        ]
    case "heyball":
        return [
            .drill(id: "heyball_women", label: "🎯 Heyball Women", style: .heyball),
            .drill(id: "heyball_men", label: "🎯 Heyball Men", style: .heyball),
        ]
    case "heyball_women":
        return [
            .leaf(system: "WPA_Heyball_Women", label: "🎯 Heyball Women (overall)", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_WorldChamp", label: "🎯 World Championship 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_Champions", label: "🎯 Champion of Champions 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_PanAmerican", label: "🎯 Pan American Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_Oceania", label: "🎯 Oceania Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_NorthAmerican", label: "🎯 North American Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_European", label: "🎯 European Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Women_Asian", label: "🎯 Asian Open 2025", style: .heyball),
        ]
    case "heyball_men":
        return [
            .leaf(system: "WPA_Heyball_Men", label: "🎯 Heyball Men (overall)", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_WorldChamp", label: "🎯 World Championship 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_Champions", label: "🎯 Champion of Champions 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_PanAmerican", label: "🎯 Pan American Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_Oceania", label: "🎯 Oceania Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_NorthAmerican", label: "🎯 North American Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_European", label: "🎯 European Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_Asian", label: "🎯 Asian Open 2025", style: .heyball),
            .leaf(system: "WPA_Heyball_Men_10Ball", label: "🎯 10-Ball World Championship 2024", style: .heyball),
        ]
    default:
        return []
    }
}
