# Test Prompts: auto

> `DCT_TOOLSET=auto`

Start the server with `DCT_TOOLSET=auto`, connect Claude Desktop (or Cursor), then run the prompts below in the same conversation thread. Auto mode starts with only 5 meta-tools — domain tools are enabled dynamically at runtime without restarting the server.

Use Claude Desktop or Cursor for these tests. VS Code Copilot requires a chat restart after `enable_toolset` and is not suitable for dynamic switching scenarios.

For confirmation-flow prompts, the first call returns `confirmation_required`. Follow up with "yes, go ahead and confirm" to execute.

---

## Meta-Tool Discovery

**list_available_toolsets**
1. List all available toolsets
2. Verify the response includes: self_service, self_service_provision, continuous_data_admin, platform_admin, reporting_insights
3. Verify each entry has a name, description, and tool_count

**get_toolset_tools**
4. Get the tools available in the self_service toolset
5. Verify the response lists tools such as vdb_tool, vdb_group_tool, dsource_tool, snapshot_tool, bookmark_tool, job_tool, timeflow_tool
6. Get the tools available in the platform_admin toolset
7. Verify the response includes tools such as engine_tool, environment_tool, iam_tool, reporting_tool

**check_operation_confirmation**
8. Check whether a POST /vdbs/{vdbId}/delete operation requires confirmation
9. Verify the response shows requires_confirmation=true and level=manual
10. Check whether a GET /vdbs/search operation requires confirmation
11. Verify the response shows requires_confirmation=false

---

## Runtime Toolset Enabling

**enable_toolset — self_service**
12. Enable the self_service toolset
13. Verify the response shows status=enabled and tools_registered > 0
14. Verify the client's tool list now includes vdb_tool and related tools (client should auto-refresh)
15. Search for all VDBs using vdb_tool
16. Get the details of the first VDB from the result
17. Get the tags for that VDB

**enable_toolset — switching toolsets**
18. Enable the reporting_insights toolset (with self_service currently active)
19. Verify the response shows previous_toolset=self_service and status=enabled
20. Verify the client's tool list no longer includes vdb_tool
21. Search the storage savings report using reporting_tool
22. Get the VDB inventory report
23. Get the license information

**enable_toolset — continuous_data_admin**
24. Enable the continuous_data_admin toolset
25. Verify the response shows status=enabled and a higher tools_registered count than self_service
26. Search for all VDBs using data_tool
27. Search for all dSources using data_tool
28. Search for all engines using engine_tool

**enable_toolset — platform_admin**
29. Enable the platform_admin toolset
30. Verify the response shows status=enabled
31. Search for all registered engines using engine_tool
32. Get the details of the first engine
33. Search for all accounts using iam_tool

---

## Toolset Disabling

**disable_toolset**
34. Disable the current toolset
35. Verify the response shows status=disabled and remaining_tools=5
36. Verify the client's tool list returns to only the 5 meta-tools
37. Attempt to use a domain tool (e.g. vdb_tool) — it should no longer be available
38. Call list_available_toolsets to confirm meta-tools still work after disabling

**disable_toolset — already minimal**
39. Call disable_toolset again when no toolset is active
40. Verify the response shows status=already_minimal

---

## Re-enabling After Disable

41. Enable self_service again after disabling
42. Verify tools_registered matches the count from step 13
43. Search for all VDBs — confirm the tool works correctly after re-enable

---

## Confirmation Flow in Auto Mode

44. Enable the self_service toolset
45. Attempt to delete a bookmark (first call — should return confirmation_required)
46. Confirm the deletion with "yes, go ahead and confirm"
47. Attempt to delete a timeflow (first call — should return confirmation_required)
48. Confirm the deletion

---

## Error Handling

49. Call enable_toolset with an invalid toolset name (e.g. "nonexistent_toolset")
50. Verify the response shows an error and lists the available toolsets
51. Call get_toolset_tools with an invalid toolset name
52. Verify the response shows an error and the available_toolsets list
53. Call check_operation_confirmation with an unknown path — verify it returns requires_confirmation=false gracefully

---

## Multi-Switch Stress

54. Enable self_service → enable platform_admin → enable reporting_insights → disable
55. After each switch, verify the tool count in the response changes appropriately
56. After the final disable, verify only 5 meta-tools remain
57. Enable continuous_data_admin and confirm data_tool and engine_tool are both present
