# Test Prompts: self_service

> `DCT_TOOLSET=self_service`

Start the server with this toolset, connect Claude Desktop, then run the prompts top to bottom in the same conversation thread. Prompts are chained — IDs discovered in earlier steps carry forward automatically.

For confirmation-flow prompts, the first call returns `confirmation_required`. Follow up with "yes, go ahead and confirm" to execute.

---

**vdb_tool**
1. Search for all VDBs
2. Get the details of the first VDB from the previous result
3. Start that VDB
4. Stop that VDB
5. Enable that VDB
6. Disable that VDB
7. Refresh that VDB by timestamp using one hour ago
8. List the snapshots for that VDB, then refresh it using the most recent snapshot
9. List the bookmarks for that VDB, then refresh it from the first bookmark in the result
10. Roll back that VDB by timestamp to two hours ago
11. Roll back that VDB using the most recent snapshot from the earlier list
12. Roll back that VDB from the first bookmark in the earlier list
13. List all snapshots for that VDB
14. List all bookmarks for that VDB
15. Get the tags for that VDB
16. Add the tag environment=test to that VDB
17. Remove the environment=test tag from that VDB

**vdb_group_tool**
18. Search for all VDB groups
19. Get the details of the first VDB group from the previous result
20. Refresh that VDB group
21. List the bookmarks for that VDB group, then refresh the group from the first bookmark
22. Refresh that VDB group by snapshot using the most recent available snapshot
23. Refresh that VDB group by timestamp to one hour ago
24. Roll back that VDB group
25. Lock that VDB group
26. Unlock that VDB group
27. Start that VDB group
28. Stop that VDB group
29. Enable that VDB group
30. Disable that VDB group
31. List the bookmarks for that VDB group
32. Get the tags for that VDB group
33. Add the tag team=qa to that VDB group
34. Remove the team=qa tag from that VDB group

**dsource_tool**
35. Search for all dSources
36. Get the details of the first dSource from the previous result
37. List all snapshots for that dSource
38. Get the tags for that dSource

**snapshot_tool**
39. Search for all snapshots
40. Get the details of the first snapshot from the previous result
41. Get the timeflow range for that snapshot
42. Get the runtime details for that snapshot
43. Find a snapshot by location using the first snapshot's location value
44. Find a snapshot by timestamp using one hour ago
45. Get the tags for that snapshot
46. Add the tag backup=true to that snapshot
47. Remove the backup=true tag from that snapshot

**bookmark_tool**
48. Search for all bookmarks
49. Get the details of the first bookmark from the previous result
50. Create a new bookmark named test-bookmark on the first VDB from earlier
51. Update that bookmark's name to test-bookmark-updated
52. Get the VDB groups associated with that bookmark
53. Get the tags for that bookmark
54. Add the tag test=true to that bookmark
55. Remove the test=true tag from that bookmark
56. Delete that bookmark (first call returns confirmation; confirm to proceed)

**job_tool**
57. Search for all jobs
58. Get the details of the first job from the previous result
59. Abandon the first running job from the search results, if any exist (first call returns confirmation; confirm to proceed)
60. Get the tags for the first job

**timeflow_tool**
61. List all timeflows
62. Search for all timeflows
63. Get the details of the first timeflow from the previous result
64. Update the name of that timeflow to test-timeflow
65. Get the snapshot day range for that timeflow
66. Repair that timeflow
67. Get the tags for that timeflow
68. Add the tag source=prod to that timeflow
69. Remove the source=prod tag from that timeflow
70. Delete that timeflow (first call returns confirmation; confirm to proceed)
