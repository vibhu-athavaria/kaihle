"use client"

import { useEffect, useState } from "react"
import { useAuth } from "../contexts/AuthContext"
import { http } from "@/lib/http"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ArrowRight, Edit } from "lucide-react"

interface Child {
  id: string
  name: string
  age: number
  grade: number | string
}

export const Dashboard: React.FC = () => {
  const { user } = useAuth()
  const [children, setChildren] = useState<Child[]>([])
  const [loading, setLoading] = useState(true)


  // -----------------------------
  // FETCH CHILDREN
  // -----------------------------
  useEffect(() => {
    const fetchChildren = async () => {
      try {
        // Use the token from axios defaults (set by AuthContext)
        const res = await http.get("/api/v1/users/me/students")

        const mappedChildren = res.data.map((child: any) => ({
          id: child.id.toString(),
          name: child.user?.full_name || "Unknown",
          username: child.user?.username || "unknown",
          age: child.age,
          grade: child.grade_level || "N/A",
        }))

        setChildren(mappedChildren)
        localStorage.setItem("children", JSON.stringify(mappedChildren))

      } catch (err) {
        console.error("Failed to fetch children:", err)
      } finally {
        setLoading(false)
      }
    }

    fetchChildren()
  }, [])

  const handleAddChild = () => {
    window.location.href = "/add-child"
  }

  const handleEditChild = (childId: string) => {
    window.location.href = `/edit-child/${childId}`
  }

  if (loading) return <div className="p-8 text-center">Loading children...</div>

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {/* Header */}
        <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between">
          <div className="text-left mb-12">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              Welcome back, {user?.full_name || "Parent"}!
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              View your children’s progress and manage their accounts.
            </p>
          </div>

          <button
            onClick={handleAddChild}
            className="bg-blue-600 text-white hover:bg-blue-700 px-6 py-3 rounded-xl font-medium transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg"
          >
            Add Child
          </button>
        </div>

        {children.length === 0 ? (
          <p className="text-gray-600">No children found.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {children.map((child) => (
              <Card
                key={child.id}
                className="overflow-hidden flex items-center justify-between p-6 shadow-md bg-blue-50 hover:shadow-lg transition-shadow duration-200"
              >
                <div className="flex-1 pr-6">
                  <h3 className="text-xl font-bold text-foreground">
                    {child.name}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    Age: {child.age} | Grade: {child.grade}
                  </p>

                  <div className="mt-4 flex gap-3">
                    <Button
                      variant="secondary"
                      className="bg-blue-600 text-white hover:bg-blue-700 px-6 py-3 rounded-xl font-medium transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg"
                    >
                      <span>View Progress</span>
                      <ArrowRight className="h-4 w-4" />
                    </Button>

                    <Button
                      variant="secondary"
                      className="bg-blue-600 text-white hover:bg-blue-700 px-6 py-3 rounded-xl font-medium transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg"
                      onClick={() => handleEditChild(child.id)}
                    >
                      <Edit className="h-4 w-4" />
                      <span>Edit</span>
                    </Button>
                  </div>
                </div>

                <Avatar
                  className="h-32 w-32 rounded-full text-white shadow-md flex items-center justify-center"
                  style={{ backgroundColor: "rgba(231, 171, 119, 1)" }}
                >
                  <AvatarFallback className="text-5xl font-bold text-black">
                    {child.name.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
