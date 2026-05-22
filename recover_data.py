#!/usr/bin/env python3
"""Data recovery script - 尽可能从对话记录恢复数据"""
import json

# 从对话中获取的数据
MODELS = [
    {"id": "model_sh-3252_1774493825784", "name": "SH"},
    {"id": "model_mr26", "name": "MR26"},
    {"id": "model_sz26", "name": "SZ26"},
    {"id": "model_qzh", "name": "QZH"},
    {"id": "model_ur", "name": "UR"},
    {"id": "model_sf", "name": "SF"},
    {"id": "model_ha6_1775108585815", "name": "HA6"},
    {"id": "model_sz老款_1775182681017", "name": "SZ老款"},
]

# SH 构建记录（从对话中 curl 获取的数据）
SH_BUILDS = [
    {
        "id": "build_1775615647040",
        "created_at": "2026-04-08T02:34:07.040Z",
        "base_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_323-20260330.30236.tgz",
        "modules": [{"name": "adas_planning", "branch": "cj/rpa/main_min_ttc_calib_rearrange_virtual_target", "commit_id": "5926913345f1048ef829b0ff7ebe4a415106d51e"}],
        "remark": "最小TTC标定虚拟障碍物",
        "pipeline_url": "https://ep.momenta.works/micro-app-maf/CIManagement/custom/pipeline/tasks/885c0eb17d2fe775070c52f6cc507c78?proc_def_key=Process_3d3decbb_e201_4d80_895e_9e46658608dd",
        "final_version": "",
        "status": "构建中",
        "test_plan": "最小TTC标定",
        "test_report": [],
        "tlm_links": [],
        "is_manual": False
    },
    {
        "id": "build_1774864259588",
        "created_at": "2026-03-30T09:50:59.588Z",
        "base_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_304-20260328.16269.tgz",
        "modules": [{"name": "adas_planning", "branch": "cj/rpa/main_min_ttc_calib_rearrange", "commit_id": "c20369c21fdc29643f335fd80216906d5b567c9f"}],
        "remark": "SH最小TTC标定测试",
        "formatted_message": "",
        "message_id": "",
        "pipeline_url": "https://ep.momenta.works/micro-app-maf/CIManagement/custom/pipeline/tasks/028adf1ac599bee6eca1ab84ec787103?proc_def_key=Process_3d3decbb_e201_4d80_895e_9e46658608dd",
        "final_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_323-20260330.30236.tgz",
        "status": "成功",
        "test_plan": "最小TTC标定",
        "test_report": [],
        "tlm_links": [],
        "is_manual": False
    },
    {
        "id": "build_1774671958988",
        "created_at": "2026-03-28T04:25:58.988Z",
        "base_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_262-20260327.14823.tgz",
        "modules": [{"name": "mff", "branch": "sky/aes_sh_vas", "commit_id": "f563bdbe5c3481910cff4835b2b57d29e8d9dd50"}],
        "remark": "SH闭环AES版本2-mff更新",
        "formatted_message": "",
        "message_id": "",
        "pipeline_url": "https://ep.momenta.works/micro-app-maf/CIManagement/custom/pipeline/tasks/305ed8c29cafad9cb13f6636edf52442?proc_def_key=Process_3d3decbb_e201_4d80_895e_9e46658608dd",
        "final_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_304-20260328.16269.tgz",
        "status": "成功",
        "test_plan": "闭环测试",
        "test_report": [],
        "tlm_links": [],
        "is_manual": False
    },
    {
        "id": "build_1774582839838",
        "created_at": "2026-03-27T03:40:39.838Z",
        "base_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_177-20260326.702.tgz",
        "modules": [
            {"name": "adas_planning", "branch": "cj/rpa/main_config_united_pr_lhs_sh_aes", "commit_id": "b4678de3b297a1e6f2292a4eb44f5de948937757"},
            {"name": "system_config_file", "branch": "vac_prd/config_value_update/MseEWuOLkr_3294", "commit_id": "acfb86b731faf5963ccb52759a7d8652f844e1f4"},
            {"name": "lhs_mcu", "branch": "mkc/lhs/r6_ESS260326", "commit_id": "5bec43417da8cfb0a862e3f4ab41d024b57b9c06"},
            {"name": "driving_control", "branch": "sh_aes_adapt/lhs/r6_0213_driving", "commit_id": "28a071dd009ace1d9676e6b7adb75fe242d5c4d1"}
        ],
        "remark": "SH闭环AES版本1",
        "formatted_message": "",
        "message_id": "",
        "pipeline_url": "https://ep.momenta.works/micro-app-maf/CIManagement/custom/pipeline/tasks/5f2e41ebeb1da68a50c074198a625885?proc_def_key=Process_3d3decbb_e201_4d80_895e_9e46658608dd",
        "final_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_262-20260327.14823.tgz",
        "status": "成功",
        "test_plan": "闭环测试",
        "test_report": ["https://mviz.momenta.works/player/v5/?meta=//ess.momenta.works/open-ui/v1/event/69c77e7d1c2c2952bcb78be2/mviz-meta", "https://mviz.momenta.works/player/v5/?meta=//ess.momenta.works/open-ui/v1/event/69c77ee81c2c2952bcb78f40/mviz-meta"],
        "tlm_links": ["https://project.feishu.cn/mainstream/tlm_requirement/detail/6931335510"],
        "is_manual": False
    },
    {
        "id": "build_1775623236055",
        "created_at": "2026-04-08T04:40:36.056Z",
        "base_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_607-20260408.11466.tgz",
        "modules": [],
        "remark": "虚拟障碍物-TTC",
        "pipeline_url": "",
        "final_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_630-20260408.20287.tgz",
        "status": "成功",
        "test_plan": "最小TTC标定",
        "test_report": [],
        "tlm_links": [],
        "is_manual": False
    }
]

# HA6 构建记录
HA6_BUILDS = [
    {
        "id": "build_manual_1775617660009",
        "created_at": "2026-04-08T03:07:40.009Z",
        "base_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.51_AE10_DBC7_21-20260405.12692.tgz",
        "modules": [
            {"name": "calib_config", "branch": "mvd_branch_HA6_2943", "commit_id": "fc650115727094bf8ff8d0f31c35f77499b664b8"},
            {"name": "driving_control", "branch": "cyf/lhs/ha6_aes_adapt_0403", "commit_id": "ba07b44cadbf6138c459d4c3504e1d0d5591e075"},
            {"name": "lhs_mcu", "branch": "mkc/lhs/r6_HA6_ESSLmt_260403", "commit_id": "9b24780d935b654063b6d4b74d4660f7abe78a5c"},
            {"name": "adas_planning", "branch": "cj/rpa/main_lhs_ha6_adapt", "commit_id": "a8c70629881c88a61c6c4a2ac37d9b54770380a6"}
        ],
        "remark": "HA6功能闭环测试",
        "pipeline_url": "https://ep.momenta.works/micro-app-maf/CIManagement/custom/pipeline/tasks/3641fa5d2e195cd8dc987035f06078df?proc_act_id=",
        "final_version": "LHUAS-V6.0.15-CCPB_X_release_1.05.51_AE10_DBC7_42-20260407.33050.tgz",
        "status": "成功",
        "test_plan": "闭环测试",
        "test_report": [],
        "tlm_links": ["https://project.feishu.cn/mainstream/tlm_requirement/detail/6944224880"],
        "is_manual": True
    }
]

# SH issue analysis 记录
SH_ISSUE_ANALYSIS = [
    {
        "id": "ia_build_1774864259588",
        "build_id": "build_1774864259588",
        "test_plan": "最小TTC标定",
        "test_version": "2026-03-30 17:50\nLHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_323-20260330.30236.tgz\nSH最小TTC标定测试",
        "test_report": "https://momenta.feishu.cn/wiki/R6Kgw9aVZiEKSNki35fcFnWHnVf",
        "test_issue": "",
        "group_chat": "",
        "created_at": "2026-03-30T09:50:59.588Z"
    },
    {
        "id": "ia_build_1774671958988",
        "build_id": "build_1774671958988",
        "test_plan": "闭环测试",
        "test_version": "2026-03-28 12:25\nLHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_304-20260328.16269.tgz\nSH闭环AES版本2-mff更新",
        "test_report": "",
        "test_issue": "",
        "group_chat": "",
        "created_at": "2026-03-28T04:25:58.988Z"
    },
    {
        "id": "ia_build_1774582839838",
        "build_id": "build_1774582839838",
        "test_plan": "闭环测试",
        "test_version": "2026-03-27 11:40\nLHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_262-20260327.14823.tgz\nSH闭环AES版本1",
        "test_report": "https://mviz.momenta.works/player/v5/?meta=//ess.momenta.works/open-ui/v1/event/69c77e7d1c2c2952bcb78be2/mviz-meta\nhttps://mviz.momenta.works/player/v5/?meta=//ess.momenta.works/open-ui/v1/event/69c77ee81c2c2952bcb78f40/mviz-meta",
        "test_issue": "",
        "group_chat": "",
        "created_at": "2026-03-27T03:40:39.838Z",
        "tlm_links": ["https://project.feishu.cn/mainstream/tlm_requirement/detail/6931335510"]
    },
    {
        "id": "ia_build_1775623236055",
        "build_id": "build_1775623236055",
        "test_plan": "最小TTC标定",
        "test_version": "2026-04-08 12:40\nLHUAS-V6.0.15-CCPB_X_release_1.05.42_AE10_DBC7_630-20260408.20287.tgz\n虚拟障碍物-TTC",
        "test_report": "",
        "test_issue": "",
        "group_chat": "",
        "tlm_links": [],
        "created_at": "2026-04-08T04:40:36.056Z"
    }
]

# HA6 TLM records
HA6_TLM = [
    {
        "id": "tlm_1775548703049",
        "description": "莲花山-AES-HA6-功能闭环适配",
        "tlm_url": "https://project.feishu.cn/mainstream/tlm_requirement/detail/6944224880",
        "tlm_title": "莲花山-AES-HA6-功能闭环适配",
        "version_info": "",  # 已被清空
        "created_at": "2026-04-07T07:58:23.049Z"
    }
]

def main():
    with open('/opt/aes-version-manager/backend/data.json', 'r') as f:
        data = json.load(f)

    ns = data['contexts']['lhs__adas__e2e-aes']

    # 恢复车型列表
    ns['models'] = MODELS

    # 恢复 SH 构建记录
    ns.setdefault('builds', {})['model_sh-3252_1774493825784'] = SH_BUILDS

    # 恢复 HA6 构建记录
    ns['builds']['model_ha6_1775108585815'] = HA6_BUILDS

    # 恢复 SH issue analysis
    ns.setdefault('issue_analysis', {})['model_sh-3252_1774493825784'] = SH_ISSUE_ANALYSIS

    # 恢复 HA6 TLM records
    ns.setdefault('tlm_records', {})['model_ha6_1775108585815'] = HA6_TLM

    # 其他集合初始化（空）
    for model in MODELS:
        mid = model['id']
        ns['builds'].setdefault(mid, [])
        ns.setdefault('branches', {}).setdefault(mid, [])
        ns.setdefault('pr_records', {}).setdefault(mid, [])
        ns.setdefault('issue_analysis', {}).setdefault(mid, [])
        ns.setdefault('tlm_records', {}).setdefault(mid, [])

    ns.setdefault('version_records', {})
    ns.setdefault('trash', [])

    with open('/opt/aes-version-manager/backend/data.json', 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print('恢复完成')
    print(f'车型: {len(MODELS)} 个')
    print(f'SH 构建: {len(SH_BUILDS)} 条')
    print(f'HA6 构建: {len(HA6_BUILDS)} 条')
    print(f'SH issue analysis: {len(SH_ISSUE_ANALYSIS)} 条')
    print('注意：SZ26/MR26/QZH/SF/UR/SZ老款 的构建数据、所有分支记录、所有PR记录已丢失，需要手动补录')

if __name__ == '__main__':
    main()
