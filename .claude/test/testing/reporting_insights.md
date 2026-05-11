# Test Prompts: reporting_insights

> `DCT_TOOLSET=reporting_insights`

This toolset is read-only. No write or destructive operations are available.

Start the server with this toolset, connect Claude Desktop, then run the prompts top to bottom in the same conversation thread.

---

**data_tool — VDB operations (read only)**
1. Search for all VDBs
2. Get the details of the first VDB from the previous result
3. List the snapshots for that VDB
4. Get the tags for that VDB

**data_tool — VDB Group operations (read only)**
5. Search for all VDB groups
6. Get the details of the first VDB group
7. List the bookmarks for that VDB group
8. Get the tags for that VDB group

**data_tool — dSource operations (read only)**
9. Search for all dSources
10. Get the details of the first dSource
11. List the snapshots for that dSource
12. Get the tags for that dSource

**snapshot_bookmark_tool — Snapshot operations (read only)**
13. Search for all snapshots
14. Get the details of the first snapshot
15. Get the capacity of the first snapshot
16. Get the timeflow range for that snapshot
17. Get the tags for that snapshot

**snapshot_bookmark_tool — Bookmark operations (read only)**
18. Search for all bookmarks
19. Get the details of the first bookmark
20. Get the VDB groups associated with that bookmark
21. Get the tags for that bookmark

**instance_tool (read only)**
22. Search for all CDBs
23. Get the details of the first CDB
24. Get the tags for that CDB
25. Search for all vCDBs
26. Get the details of the first vCDB
27. Get the tags for that vCDB

**database_template_tool (read only)**
28. Search for all database templates
29. Get the details of the first database template
30. Get the tags for that database template

**hook_template_tool (read only)**
31. Search for all hook templates
32. Get the details of the first hook template
33. Get the tags for that hook template

**virtualization_policy_tool (read only)**
34. Search for all virtualization policies
35. Get the details of the first virtualization policy
36. Get the tags for that policy

**job_tool (read only)**
37. Search for all jobs
38. Get the details of the first job
39. Get the result of the first completed job
40. Get the tags for the first job

**engine_tool (read only)**
41. Search for all registered engines
42. Get the details of the first engine
43. Get the tags for that engine

**environment_tool (read only)**
44. Search for all environments
45. Get the details of the first environment
46. List the hosts in that environment
47. List the listeners in that environment
48. Get the tags for that environment

**source_tool (read only)**
49. Search for all sources
50. Get the details of the first source
51. Get the tags for that source

**reporting_tool**
52. Search the storage savings report
53. Get the storage capacity report
54. Get the virtualization storage summary report
55. Get the VDB inventory report
56. Search the VDB inventory report
57. Get the dSource consumption report
58. Get the engine performance analytics report
59. Get the dataset performance analytics report
60. Get the API usage report
61. Get the audit logs summary report
62. Get the license information
63. Get the virtualization jobs history
64. Search the virtualization jobs history for the last 7 days
65. Get the virtualization actions history
66. Search the virtualization actions history for the last 7 days
67. Get the virtualization faults history
68. Search the virtualization faults history for the last 7 days
69. Get the virtualization alerts history
70. Search the virtualization alerts history for the last 7 days
71. Search for all scheduled reports
72. Get the details of the first scheduled report

**data_connection_tool (read only)**
73. Search for all data connections
74. Get the details of the first data connection
75. Get the tags for that data connection

**tag_tool (read only)**
76. Search for all tags
77. Get the details of the first tag
78. Get the usages of that tag
79. Search the usages of that tag
